import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

# Flask alkalmazás létrehozása
app = Flask(__name__)

# OpenAI API kulcs beállítása környezeti változóból (vagy itt közvetlenül is megadhatod)
api_key = os.getenv("ASSISTANT_KEY")  # vagy használd: api_key = 'your_api_key'
client = OpenAI(api_key=api_key)

def parse_response_to_json(response_text):
    # Számla adatainak feldolgozása
    invoice_data = {
        "Invoice Date": "",
        "PO Number": "",
        "Seller Company Name": "",
        "Seller Company Address": "",
        "Seller Tax No.": "",
        "Buyer Company Name": "",
        "Buyer Company Address": "",
        "Buyer Tax No.": "",
        "Items": [],
        "VAT percent": "",
        "Subtotal excluded VAT": "",
        "Total included VAT": "",
        "Shipping Cost": ""
    }

    lines = response_text.split("\n")
    current_item = {}
    for line in lines:
        line = line.strip()
        if ": " in line:
            key_value = line.split(": ", 1)
            if len(key_value) == 2:
                key, value = key_value
                if "Invoice Date" in key:
                    invoice_data["Invoice Date"] = value
                elif "PO Number" in key:
                    invoice_data["PO Number"] = value
                elif "Seller Company Name" in key:
                    invoice_data["Seller Company Name"] = value
                elif "Seller Company Address" in key:
                    invoice_data["Seller Company Address"] = value
                elif "Seller Tax No." in key:
                    invoice_data["Seller Tax No."] = value
                elif "Buyer Company Name" in key:
                    invoice_data["Buyer Company Name"] = value
                elif "Buyer Company Address" in key:
                    invoice_data["Buyer Company Address"] = value
                elif "Buyer Tax No." in key:
                    invoice_data["Buyer Tax No."] = value
                elif "Description" in key:
                    if current_item:
                        invoice_data["Items"].append(current_item)
                    current_item = {"description": value}
                elif "Quantity" in key:
                    current_item["quantity"] = value
                elif "Price" in key:
                    current_item["price"] = value
                elif "Amount" in key:
                    current_item["amount"] = value
                elif "Discounts" in key:
                    current_item["discount"] = value
                elif "VAT percent" in key:
                    invoice_data["VAT percent"] = value
                elif "Subtotal excluded VAT" in key:
                    invoice_data["Subtotal excluded VAT"] = value
                elif "Total included VAT" in key:
                    invoice_data["Total included VAT"] = value
                elif "Shipping Cost" in key:
                    invoice_data["Shipping Cost"] = value
    
    if current_item:
        invoice_data["Items"].append(current_item)

    return invoice_data

def extract_invoice_data(json_data):
    # OpenAI API meghívása a számla adatok felismeréséhez
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # vagy gpt-3.5-turbo
        messages=[
            {
                "role": "system",
                "content": "You are an AI that extracts invoice data."
            },
            {
                "role": "user",
                "content": f"Extract the following information from the invoice JSON:\n\n"
                           f"1. Invoice Date\n"
                           f"2. PO Number\n"
                           f"3. Seller Company Name\n"
                           f"4. Seller Company Address\n"
                           f"5. Seller Tax No.\n"
                           f"6. Buyer Company Name\n"
                           f"7. Buyer Company Address\n"
                           f"8. Buyer Tax No.\n"
                           f"9. Items (including description, quantity, price, amount, and any discounts)\n"
                           f"10. VAT percent\n"
                           f"11. Subtotal excluded VAT\n"
                           f"12. Total included VAT\n"
                           f"13. Shipping Cost\n\n"
                           f"JSON Data:\n{json.dumps(json_data)}"
            }
        ]
    )
    
    # Az eredmény kinyerése az OpenAI válaszból
     response_text = (response.choices[0].message.content)

    # A válasz feldolgozása és JSON formátumra alakítása
    invoice_data = parse_response_to_json(response_text)

    return invoice_data

@app.route('/upload_json', methods=['POST'])
def upload_json():
    # JSON fájl fogadása
    json_data = request.json
    if not json_data:
        return "No JSON data found", 400
    
    # Számla adatok kinyerése OpenAI segítségével
    invoice_data = extract_invoice_data(json_data)
    
    # Számla adatok visszaadása JSON formátumban
    return jsonify(invoice_data)

# Webszerver indítása
if __name__ == '__main__':
    app.run(debug=True)
