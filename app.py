import os
import json
import pandas as pd
from flask import Flask, request, send_file
from openai import OpenAI
import io

# Flask alkalmazás létrehozása
app = Flask(__name__)

# OpenAI API kulcs beállítása közvetlenül a kódban

api_key = os.getenv("ASSISTANT_KEY")
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

def save_to_excel(invoice_data):
    output = io.BytesIO()  # Létrehozunk egy memóriába író objektumot
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_main = pd.DataFrame([{
            "Field": "Invoice Date", "Value": invoice_data.get("Invoice Date")
        }, {
            "Field": "PO Number", "Value": invoice_data.get("PO Number")
        }, {
            "Field": "Seller Company Name", "Value": invoice_data.get("Seller Company Name")
        }, {
            "Field": "Seller Company Address", "Value": invoice_data.get("Seller Company Address")
        }, {
            "Field": "Seller Tax No.", "Value": invoice_data.get("Seller Tax No.")
        }, {
            "Field": "Buyer Company Name", "Value": invoice_data.get("Buyer Company Name")
        }, {
            "Field": "Buyer Company Address", "Value": invoice_data.get("Buyer Company Address")
        }, {
            "Field": "Buyer Tax No.", "Value": invoice_data.get("Buyer Tax No.")
        }])
        df_main.to_excel(writer, sheet_name='Invoice', index=False)

        df_items = pd.DataFrame(invoice_data.get("Items", []))
        df_items.to_excel(writer, sheet_name='Invoice', startrow=len(df_main) + 2, index=False)

        df_vat_summary = pd.DataFrame([{
            "Field": "VAT percent", "Value": invoice_data.get("VAT percent")
        }, {
            "Field": "Subtotal excluded VAT", "Value": invoice_data.get("Subtotal excluded VAT")
        }, {
            "Field": "Total included VAT", "Value": invoice_data.get("Total included VAT")
        }, {
            "Field": "Shipping Cost", "Value": invoice_data.get("Shipping Cost")
        }])
        df_vat_summary.to_excel(writer, sheet_name='Invoice', startrow=len(df_main) + len(df_items) + 5, index=False)
    
    output.seek(0)  # Visszaállítjuk az íráspozíciót a fájl elejére
    return output

@app.route('/upload_json', methods=['POST'])
def upload_json():
    # JSON fájl fogadása
    json_data = request.json
    if not json_data:
        return "No JSON data found", 400
    
    # Számla adatok kinyerése
    invoice_data = parse_response_to_json(json.dumps(json_data))  # Egyszerűsítve
    
    # Excel fájl generálása
    excel_data = save_to_excel(invoice_data)
    
    # Excel fájl küldése letöltésre
    return send_file(excel_data, download_name='invoice.xlsx', as_attachment=True)

# Webszerver indítása
if __name__ == '__main__':
    app.run(debug=True)
