from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ✅ Chiave API presa da Render
ABOUTYOU_API_KEY = os.getenv("ABOUTYOU_API_KEY")

ABOUTYOU_URL_STOCK = "https://partner.aboutyou.com/api/v1/products/stocks"
ABOUTYOU_URL_PRICE = "https://partner.aboutyou.com/api/v1/products/prices"
ABOUTYOU_URL_PRODUCTS = "https://partner.aboutyou.com/api/v1/products"

@app.route('/shopify-webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        print("❌ Nessun payload ricevuto")
        return jsonify({"error": "no data"}), 400

    print("=== 📦 NUOVO WEBHOOK RICEVUTO ===")
    print(data)

    sku = None
    quantity = None
    price = None

    # INVENTORY LEVEL UPDATE
    if "inventory_item_id" in data and "available" in data:
        sku = data.get("sku")
        quantity = data.get("available")
        print(f"📦 INVENTORY update: SKU={sku}, qty={quantity}")

    # PRODUCT UPDATE
    elif "variants" in data and isinstance(data["variants"], list):
        for variant in data["variants"]:
            if variant.get("sku"):
                sku = variant.get("sku")
                quantity = variant.get("inventory_quantity", 0)
                price = variant.get("price")
                print(f"🧩 PRODUCT update: SKU={sku}, qty={quantity}, price={price}")
                break

    if not sku:
        print("⚠️ Nessuno SKU trovato nel payload.")
        return jsonify({"error": "missing sku"}), 400

    headers = {"Content-Type": "application/json", "X-API-Key": ABOUTYOU_API_KEY}

    # Aggiornamento giacenza
    if quantity is not None:
        payload_stock = {"items": [{"sku": sku, "quantity": quantity}]}
        r = requests.put(ABOUTYOU_URL_STOCK, json=payload_stock, headers=headers)
        print(f"🔄 STOCK UPDATE → {r.status_code}: {r.text[:250]}")

        if r.status_code == 404:
            print(f"🆕 SKU {sku} non esiste. Creo nuovo prodotto su AboutYou...")
            create_payload = {
                "items": [{
                    "sku": sku,
                    "name": sku,
                    "country_code": "DE",
                    "brand": "Cammarata",
                    "active": True
                }]
            }
            create = requests.post(ABOUTYOU_URL_PRODUCTS, json=create_payload, headers=headers)
            print(f"✅ Creato nuovo prodotto: {create.status_code}")

    # Aggiornamento prezzo
    if price is not None:
        payload_price = {
            "items": [{
                "sku": sku,
                "price": {"country_code": "DE", "retail_price": price, "sale_price": None}
            }]
        }
        r2 = requests.put(ABOUTYOU_URL_PRICE, json=payload_price, headers=headers)
        print(f"💶 PRICE UPDATE → {r2.status_code}: {r2.text[:250]}")

    return jsonify({"status": "ok"}), 200


@app.route('/', methods=['GET'])
def home():
    return "✅ Sync attivo tra Shopify e AboutYou", 200


@app.route('/import-products', methods=['GET'])
def import_products():
    """Test manuale per aggiornare prezzi e giacenze"""
    headers = {"X-API-Key": ABOUTYOU_API_KEY, "Content-Type": "application/json"}

    test_sku = "TESTSKU123"
    test_price = 99.99
    test_qty = 3

    payload_stock = {"items": [{"sku": test_sku, "quantity": test_qty}]}
    payload_price = {
        "items": [{
            "sku": test_sku,
            "price": {"country_code": "DE", "retail_price": test_price, "sale_price": None}
        }]
    }

    r1 = requests.put(ABOUTYOU_URL_STOCK, json=payload_stock, headers=headers)
    r2 = requests.put(ABOUTYOU_URL_PRICE, json=payload_price, headers=headers)

    return jsonify({
        "sku": test_sku,
        "stock_update": r1.status_code,
        "price_update": r2.status_code
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
