from flask import Flask, request, jsonify
import requests
import os
import time  # ⏱️ Aggiunto per evitare "Too many requests"

app = Flask(__name__)

# ======================
# 🔑 Variabili d'ambiente (da Render)
# ======================
ABOUTYOU_API_KEY = os.getenv("ABOUTYOU_API_KEY")
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")

# ======================
# 🌐 Endpoint AboutYou API
# ======================
ABOUTYOU_URL_PRODUCTS = "https://partner.aboutyou.com/api/v1/products"
ABOUTYOU_URL_STOCK = "https://partner.aboutyou.com/api/v1/products/stocks"
ABOUTYOU_URL_PRICE = "https://partner.aboutyou.com/api/v1/products/prices"


# ======================
# 🔄 Sincronizzazione completa Shopify → AboutYou
# ======================
def sync_all_products():
    """Sincronizza tutti i prodotti Shopify → AboutYou"""
    print("🚀 Avvio sincronizzazione completa da Shopify...")

    headers_shopify = {"X-Shopify-Access-Token": SHOPIFY_API_KEY}
    headers_aboutyou = {"X-API-Key": ABOUTYOU_API_KEY, "Content-Type": "application/json"}

    url_shopify = f"{SHOPIFY_STORE}/admin/api/2025-01/products.json?limit=250"
    response = requests.get(url_shopify, headers=headers_shopify)

    if response.status_code != 200:
        print(f"❌ Errore API Shopify: {response.status_code}")
        return

    products = response.json().get("products", [])
    print(f"🧩 Trovati {len(products)} prodotti su Shopify")

    for product in products:
        for variant in product.get("variants", []):
            sku = variant.get("sku")
            price = variant.get("price")
            qty = variant.get("inventory_quantity", 0)

            if not sku:
                continue

            # Aggiorna giacenza
            stock_payload = {"items": [{"sku": sku, "quantity": qty}]}
            stock_res = requests.put(ABOUTYOU_URL_STOCK, json=stock_payload, headers=headers_aboutyou)
            print(f"📦 Stock aggiornato → {sku}: {qty}pz → {stock_res.status_code}")

            # 🕐 Pausa 1 secondo per evitare limiti API
            time.sleep(1)

            # Aggiorna prezzo
            price_payload = {
                "items": [{
                    "sku": sku,
                    "price": {"country_code": "DE", "retail_price": price, "sale_price": None}
                }]
            }
            price_res = requests.put(ABOUTYOU_URL_PRICE, json=price_payload, headers=headers_aboutyou)
            print(f"💶 Prezzo aggiornato → {sku}: {price}€ → {price_res.status_code}")

            # 🕐 Pausa 1 secondo anche dopo l’update del prezzo
            time.sleep(1)

    print("🎯 Sincronizzazione completa terminata.")


# ======================
# 🔔 Webhook Shopify (evento singolo)
# ======================
@app.route('/shopify-webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        print("❌ Nessun payload ricevuto")
        return jsonify({"error": "no data"}), 400

    print("=== 📦 WEBHOOK RICEVUTO ===")
    print(data)

    sku = None
    quantity = None
    price = None

    # Tipo: aggiornamento giacenza
    if "inventory_item_id" in data and "available" in data:
        sku = data.get("sku")
        quantity = data.get("available")

    # Tipo: aggiornamento prodotto
    elif "variants" in data:
        for variant in data["variants"]:
            if variant.get("sku"):
                sku = variant["sku"]
                quantity = variant.get("inventory_quantity", 0)
                price = variant.get("price")
                break

    if not sku:
        return jsonify({"error": "missing sku"}), 400

    headers = {"Content-Type": "application/json", "X-API-Key": ABOUTYOU_API_KEY}

    # Aggiorna stock
    if quantity is not None:
        stock_payload = {"items": [{"sku": sku, "quantity": quantity}]}
        r1 = requests.put(ABOUTYOU_URL_STOCK, json=stock_payload, headers=headers)
        print(f"🔄 Stock update {sku}: {quantity} → {r1.status_code}")

        # Se SKU non esiste, lo crea
        if r1.status_code == 404:
            create_payload = {
                "items": [{
                    "sku": sku,
                    "name": sku,
                    "brand": "Cammarata",
                    "country_code": "DE",
                    "active": True
                }]
            }
            requests.post(ABOUTYOU_URL_PRODUCTS, json=create_payload, headers=headers)
            requests.put(ABOUTYOU_URL_STOCK, json=stock_payload, headers=headers)

    # 🕐 Pausa 1 secondo per sicurezza
    time.sleep(1)

    # Aggiorna prezzo
    if price is not None:
        price_payload = {
            "items": [{
                "sku": sku,
                "price": {"country_code": "DE", "retail_price": price, "sale_price": None}
            }]
        }
        r2 = requests.put(ABOUTYOU_URL_PRICE, json=price_payload, headers=headers)
        print(f"💶 Price update {sku}: {price}€ → {r2.status_code}")

    return jsonify({"status": "ok"}), 200


# ======================
# 🧪 Test manuale (SKU reale)
# ======================
@app.route('/import-products', methods=['GET'])
def import_products():
    sku = request.args.get("sku")
    qty = request.args.get("qty", type=int, default=0)
    price = request.args.get("price", type=float, default=0.0)

    if not sku:
        return jsonify({"error": "missing sku"}), 400

    headers = {"X-API-Key": ABOUTYOU_API_KEY, "Content-Type": "application/json"}

    stock_payload = {"items": [{"sku": sku, "quantity": qty}]}
    price_payload = {
        "items": [{
            "sku": sku,
            "price": {"country_code": "DE", "retail_price": price, "sale_price": None}
        }]
    }

    # 1️⃣ Aggiorna giacenza
    r1 = requests.put(ABOUTYOU_URL_STOCK, json=stock_payload, headers=headers)

    # 🕐 2️⃣ Aspetta 3 secondi per non essere bloccato
    import time
    time.sleep(3)

    # 3️⃣ Aggiorna prezzo
    r2 = requests.put(ABOUTYOU_URL_PRICE, json=price_payload, headers=headers)

    return jsonify({
        "sku": sku,
        "qty": qty,
        "price": price,
        "stock_update": r1.status_code,
        "price_update": r2.status_code,
        "stock_response": r1.text[:200],
        "price_response": r2.text[:200]
    })

# ======================
# 🌍 Rotte varie
# ======================
@app.route('/', methods=['GET'])
def home():
    return "✅ Sync Shopify ↔️ AboutYou attivo", 200


@app.route('/sync-all', methods=['GET'])
def sync_all():
    sync_all_products()
    return jsonify({"status": "sync complete"}), 200


# ======================
# 🚀 Avvio app
# ======================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

