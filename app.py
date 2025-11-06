from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Legge la chiave API dalle variabili d’ambiente di Render
ABOUTYOU_API_KEY = os.getenv("ABOUTYOU_API_KEY")
ABOUTYOU_URL_STOCK = "https://partner.aboutyou.com/api/v1/products/stocks"
ABOUTYOU_URL_PRICE = "https://partner.aboutyou.com/api/v1/products/prices"
ABOUTYOU_URL_PRODUCTS = "https://partner.aboutyou.com/api/v1/products"

@app.route('/shopify-webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    print("=== RICEVUTO WEBHOOK DA SHOPIFY ===")
    print(data)

    # Estraggo SKU, quantità e prezzo
    sku = None
    quantity = None
    price = None

    if "inventory_item_id" in data:
        sku = data.get("sku")
        quantity = data.get("available", 0)
    elif "variants" in data and data["variants"]:
        sku = data["variants"][0].get("sku")
        price = data["variants"][0].get("price")

    if not sku:
        print("⚠️ Nessuno SKU trovato nel payload")
        return jsonify({"error": "missing sku"}), 400

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": ABOUTYOU_API_KEY
    }

    # 🔹 Aggiorna quantità se presente
    if quantity is not None:
        payload_stock = {"items": [{"sku": sku, "quantity": quantity}]}
        r = requests.put(ABOUTYOU_URL_STOCK, json=payload_stock, headers=headers)
        print(f"🔄 Aggiornamento STOCK → SKU {sku} → quantità {quantity} | Risposta {r.status_code} {r.text}")

        # Se lo SKU non esiste, lo crea automaticamente
        if r.status_code == 404:
            print(f"⚙️ SKU {sku} non trovato — provo a creare il prodotto su AboutYou...")
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
            print(f"🆕 Creato nuovo prodotto → {create.status_code} {create.text}")

    # 🔹 Aggiorna prezzo se presente
    if price is not None:
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
        print(f"💶 Aggiornamento PREZZO → SKU {sku} → prezzo {price} | Risposta {r2.status_code} {r2.text}")

    return jsonify({"status": "ok"}), 200


@app.route('/', methods=['GET'])
def home():
    return "Shopify → AboutYou Sync attivo ✅", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
