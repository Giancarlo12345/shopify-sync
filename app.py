from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

ABOUTYOU_API_KEY = "kmfB3Cgf.3jsfGicL3kbRwZCrbxfuJCcDqmVGCxT9jLU84EIdcKJdFQs7MY5All39"
ABOUTYOU_URL_STOCK = "https://partner.aboutyou.com/api/v1/products/stocks"
ABOUTYOU_URL_PRICE = "https://partner.aboutyou.com/api/v1/products/prices"

@app.route('/shopify-webhook', methods=['POST'])
def handle_webhook():
    data = request.get_json()

    if not data:
        return jsonify({"error": "no data"}), 400

    if "inventory_item_id" in data:
        sku = data.get("sku")
        quantity = data.get("available", 0)
        payload = {"items": [{"sku": sku, "quantity": quantity}]}
        url = ABOUTYOU_URL_STOCK
    else:
        sku = data.get("variants", [{}])[0].get("sku")
        price = float(data.get("variants", [{}])[0].get("price") or 0)
        payload = {
            "items": [{
                "sku": sku,
                "price": {
                    "country_code": "DE",
                    "retail_price": price,
                    "sale_price": None
                }
            }]
        }
        url = ABOUTYOU_URL_PRICE

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": ABOUTYOU_API_KEY
    }

    r = requests.put(url, json=payload, headers=headers)
    print("Aggiornamento inviato a AboutYou:", r.status_code, r.text)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
