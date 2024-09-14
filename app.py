import os
import json
from flask import Flask, request, jsonify
from google.api_core.client_options import ClientOptions
from google.cloud import documentai  # type: ignore
from openai import OpenAI
from typing import Optional

# Flask alkalmazás létrehozása
app = Flask(__name__)

# OpenAI API kulcs beállítása
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# GCP hitelesítési fájl létrehozása a környezeti változóból
def create_gcp_credentials_file():
    credentials_json = os.getenv("GCP_CREDENTIALS")
    if credentials_json:
        credentials_path = "/tmp/credentials.json"  # Átmeneti fájl
        with open(credentials_path, "w") as f:
            f.write(credentials_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    else:
        raise Exception("No GCP credentials found in environment variable.")

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



def process_document_sample(project_id: str, location: str, processor_id: str, file_path: str, mime_type: str) -> str:
    # Hitelesítési fájl létrehozása
    create_gcp_credentials_file()
    
    # Google Document AI feldolgozás
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    name = client.processor_path(project_id, location, processor_id)

    # PDF fájl beolvasása
    with open(file_path, "rb") as pdf_file:
        pdf_content = pdf_file.read()

    # RawDocument létrehozása
    raw_document = documentai.RawDocument(content=pdf_content, mime_type=mime_type)

    # Document AI ProcessRequest létrehozása
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)

    # A feldolgozási kérés elküldése a Document AI-hoz
    result = client.process_document(request=request)
    
    # Dokumentum szöveges tartalmának kinyerése
    document_text = result.document.text

    return document_text

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    # PDF fájl fogadása
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    pdf_file = request.files.get('file')
    
    if pdf_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Fájl mentése átmenetileg
    file_path = os.path.join(os.getcwd(), pdf_file.filename)
    pdf_file.save(file_path)

    # Google Document AI paraméterek
    project_id = "gifted-country-324010"
    location = "us"
    processor_id = "e0bb021f188ca0d8"
    mime_type = "application/pdf"

    # OCR futtatása a Google Document AI segítségével
    document_text = process_document_sample(project_id, location, processor_id, file_path, mime_type)

    # Logoljuk a kinyert OCR szöveget
    print("Google Document AI extracted text:", document_text)

    # Az átmenetileg mentett fájl törlése
    os.remove(file_path)

    # OpenAI feldolgozás a visszakapott OCR szöveg alapján
    invoice_data = extract_invoice_data(document_text)

    # Számla adatok visszaküldése JSON formátumban
    return jsonify(invoice_data)

def extract_invoice_data(document_text):
    # Logoljuk a szöveget, amit az OpenAI-nak küldünk
    print("Text being sent to OpenAI:", document_text)
    
    # OpenAI API meghívása a számla adatok felismeréséhez
    response = client.chat.completions.create(
        model="gpt-4o-mini",  
        messages=[
            {
                "role": "system",
                "content": "You are an AI that extracts invoice data. Only give back the exact data, nothing else!"
            },
            {
                "role": "user",
                "content": f"Here is the text of an invoice. Extract the following information:\n"
                           f"1. Invoice Date\n"
                           f"2. PO Number\n"
                           f"3. Seller Company Name\n"
                           f"4. Seller Company Address\n"
                           f"5. Seller Tax No.\n"
                           f"6. Buyer Company Name\n"
                           f"7. Buyer Company Address\n"
                           f"8. Buyer Tax No.\n"
                           f"9. Items with structured information(description, quantity, unit, price, full amount)\n"
                           f"10. VAT percent - IF THERE IS NO VAT INFORMATION, GIVE BACK - CHARACTER \n"
                           f"11. Subtotal excluded VAT\n"
                           f"12. Total included VAT\n"
                           f"13. Shipping Cost - IF THERE IS NO SHIPPING COST, GIVE BACK - CHARACTER!\n\n"
                           f"Text of the invoice:\n{document_text}"
            }
        ]
    )
    
    # Az eredmény kinyerése az OpenAI válaszból
    response_text = response.choices[0].message.content

    # A válasz feldolgozása és JSON formátumra alakítása
    invoice_data = parse_response_to_json(response_text)

    return invoice_data



# Webszerver indítása
if __name__ == '__main__':
    app.run(debug=True)
