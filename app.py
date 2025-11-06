from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Chiavi ambiente
ABOUTYOU_API_KEY = os.getenv("ABOUTYOU_API_KEY")
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")

ABOUTYOU_URL_STOCK = "https://partner.aboutyou.com/api/v1/products/stocks"
ABOUTYOU_URL_PRICE = "https://partner.aboutyou.com/api/v1/products/prices"
ABOUTYOU_URL_PRODUCTS = "https://partner.aboutyou.com/api/v1/products"


# ======================
# 1️⃣ Import da Shopify a AboutYou
# ======================

def get_products_from_shopify():
    headers = {"X-Shopify-Access-Token": SHOPIFY_API_KEY}
    url = f"{SHOPIFY_STORE}/admin/api/2025-01/products.json?limit=50"
    r = requests.get(url, headers=headers)
    print(f"📦 Lettura prodotti Shopify → {r.status_code}")
    return r.json().get("products", [])


def sync_product_to_aboutyou(product):
    """Crea o aggiorna prodotto su AboutYou"""
    for variant in product.get("variants", []):
        sku = variant.get("sku")
        if not sku:
            continue
        name = product.get("title")
        brand = product.get("vendor", "ShopifySync")
        price = variant.get("price")
        qty = variant.get("inventory_quantity", 0)

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": ABOUTYOU_API_KEY
        }

        # Aggiorna stock
        payload_stock = {"items": [{"sku": sku, "quantity": qty}]}
        r1 = requests.put(ABOUTYOU_URL_STOCK, json=payload_stock, headers=headers)

        # Se lo SKU non esiste, lo crea
        if r1.status_code == 404:
            payload_create = {
                "items": [{
                    "sku": sku,
                    "name": name,
                    "brand": brand,
                    "country_code": "DE",
                    "active": True
                }]
            }
            create = requests.post(ABOUTYOU_URL_PRODUCTS, json=payload_create, headers=headers)
            print(f"🆕 Creato {sku} → {create.status_code}")

        # Aggiorna prezzo
        payload_price = {
            "items": [{
                "sku": sku,
                "price": {
                    "country_code": "DE",
                    "retail_price": price,
                    "sale_price": None
                }
            }]
        }
        r2 = requests.put(ABOUTYOU_URL_PRICE, json=payload_price, headers=headers)
        print(f"💶 Prezzo {sku} aggiornato → {r2.status_code}")

        print(f"✅ Sync completato → {sku}: {qty}pz a {price}€")


@app.route('/import-products', methods=['GET'])
def import_products():
    products = get_products_from_shopify()
    for p in products:
        sync_product_to_aboutyou(p)
    return jsonify({"imported": len(products)}), 200


# ======================
# 2️⃣ Webhook per aggiornamenti automatici
# ======================

@app.route('/shopify-webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "no data"}), 400

    print("=== 🔔 WEBHOOK RICEVUTO ===")
    print(data)

    sku = None
    quantity = None
    price = None

    if "inventory_item_id" in data and "available" in data:
        sku = data.get("sku")
        quantity = data.get("available")

    elif "variants" in data and isinstance(data["variants"], list):
        for v in data["variants"]:
            sku = v.get("sku")
            quantity = v.get("inventory_quantity", 0)
            price = v.get("price")

    if not sku:
        return jsonify({"error": "missing sku"}), 400

    headers = {"Content-Type": "application/json", "X-API-Key": ABOUTYOU_API_KEY}

    if quantity is not None:
        payload_stock = {"items": [{"sku": sku, "quantity": quantity}]}
        requests.put(ABOUTYOU_URL_STOCK, json=payload_stock, headers=headers)

    if price is not None:
        payload_price = {
            "items": [{
                "sku": sku,
                "price": {"country_code": "DE", "retail_price": price, "sale_price": None}
            }]
        }
        requests.put(ABOUTYOU_URL_PRICE, json=payload_price, headers=headers)

    print(f"✅ Aggiornato {sku} → qty {quantity}, prezzo {price}")
    return jsonify({"status": "ok"}), 200


@app.route('/', methods=['GET'])
def home():
    return "✅ Shopify → AboutYou Sync attivo", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
