import os
import json
from flask import Flask, request, jsonify
from google.api_core.client_options import ClientOptions
from google.cloud import documentai  # type: ignore
import openai
from openai import OpenAI

# Flask alkalmazás létrehozása
app = Flask(__name__)

# OpenAI API kulcs beállítása környezeti változóból
api_key = os.getenv("ASSISTANT_KEY")
openai.api_key = api_key  # Beállítjuk az OpenAI API kulcsot
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
    return jsonify(invoice_data), 200



def extract_invoice_data(document_text):
    print("Text being sent to OpenAI:", document_text)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI that extracts invoice data. Only give back the exact information, no another talk!"
                },
                {
                    "role": "user",
                    "content": (
                        "Here is the text of an invoice. Please extract the following information as structured data:\n"
                        "1. Invoice Date (if not present, return '-')\n"
                        "2. PO Number (if not present, return '-')\n"
                        "3. Seller Company Name (if not present, return '-')\n"
                        "4. Seller Company Address (if not present, return '-')\n"
                        "5. Seller Tax No. (if not present, return '-')\n"
                        "6. Buyer Company Name (if not present, return '-')\n"
                        "7. Buyer Company Address (if not present, return '-')\n"
                        "8. Buyer Tax No. (if not present, return '-')\n"
                        "9. Items with structured information (if items are not present, return '-'): \n"
                        "   - description as 'description'\n"
                        "   - quantity (without unit) as 'quantity'\n"
                        "   - unit as 'unit'\n"
                        "   - price per unit as 'price'\n"
                        "   - full amount as 'amount'\n"
                        "10. VAT percent (if there is no VAT information, return '-')\n"
                        "11. Subtotal excluded VAT (if not present, return '-')\n"
                        "12. Total included VAT (if not present, return '-')\n"
                        "13. Shipping Cost (if not present, return '-')\n\n"
                        f"Text of the invoice:\n{document_text}"
                    )
                }
            ]
        )

        response_text = (response.choices[0].message.content)
        print("Full OpenAI response:", response_text)

        # Tisztítási művelet az OpenAI válaszán
        cleaned_response_text = response_text.replace("```json", "").replace("```", "").strip()
        print("Cleaned response text after extra cleaning:", cleaned_response_text)

        # A JSON string átalakítása strukturált JSON adatformává
        structured_data = json.loads(cleaned_response_text)
        return structured_data

    except Exception as e:
        print(f"An error occurred during OpenAI API call: {e}")
        return {"error": "Failed to extract invoice data."}



# Webszerver indítása
if __name__ == '__main__':
    app.run(debug=True)
