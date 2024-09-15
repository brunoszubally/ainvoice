import os
import json
from flask import Flask, request, jsonify
from google.api_core.client_options import ClientOptions
from google.cloud import documentai  # type: ignore
import openai
from PyPDF2 import PdfReader

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

def process_document_sample(project_id: str, location: str, processor_id: str, file_path: str, mime_type: str) -> list:
    """PDF fájl feldolgozása oldalanként Google Document AI segítségével"""
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

    # Dokumentum szöveges tartalmának kinyerése oldalanként
    pages_text = [page.layout.text for page in result.document.pages]

    return pages_text

def extract_pdf_pages(pdf_path):
    """Kinyeri a PDF oldalainak szövegét egy listába."""
    reader = PdfReader(pdf_path)
    pages = []

    # Az összes oldal bejárása és szöveg kinyerése
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        text = page.extract_text()
        pages.append(text)
    
    return pages

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

    # PDF oldalainak feldolgozása Google Document AI segítségével
    document_pages = process_document_sample(project_id, location, processor_id, file_path, mime_type)

    # Logoljuk a kinyert OCR szöveget
    print("Google Document AI extracted text from pages:", document_pages)

    # Az átmenetileg mentett fájl törlése
    os.remove(file_path)

    # Oldalankénti OpenAI feldolgozás
    invoice_data = extract_invoice_data_per_page(document_pages)

    # Számla adatok visszaküldése JSON formátumban
    return jsonify(invoice_data), 200


def extract_invoice_data_per_page(document_pages):
    """Oldalanként dolgozza fel az OCR szöveget az OpenAI API-n keresztül."""
    full_response = []

    for page_num, page_text in enumerate(document_pages):
        print(f"Processing page {page_num + 1} of {len(document_pages)}")

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI that extracts invoice data."
                    },
                    {
                        "role": "user",
                        "content": (
                            "Here is part of the text of an invoice. Please extract the following information as structured data:\n"
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
                            f"Text of the invoice:\n{page_text}"
                        )
                    }
                ]
            )

            response_text = response.choices[0].message.content
            print(f"OpenAI response for page {page_num + 1}:", response_text)

            # Tisztítási művelet
            cleaned_response_text = response_text.replace("```json", "").replace("```", "").strip()
            full_response.append(json.loads(cleaned_response_text))

        except Exception as e:
            print(f"An error occurred on page {page_num + 1}: {e}")
            full_response.append({"error": f"Failed to process page {page_num + 1}"})

    return merge_responses(full_response)

def merge_responses(responses):
    """Összefésüli a válaszokat, hogy egy struktúrált JSON-t adjon vissza."""
    if not responses:
        return {}

    final_response = responses[0]  # Az első válaszból indulunk ki

    # Több részből álló tételek (Items) összeillesztése
    all_items = []
    for response in responses:
        if "Items" in response and response["Items"] != "-":
            all_items.extend(response["Items"])

    final_response["Items"] = all_items if all_items else "-"

    return final_response


# Webszerver indítása
if __name__ == '__main__':
    app.run(debug=True)
