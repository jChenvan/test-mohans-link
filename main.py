import asyncio
from typing import Optional
import google.generativeai as genai
import json
import os
import time
from dotenv import load_dotenv
import requests

from fetch_site import fetch_site
load_dotenv()

URL = "https://pbicanada.org/2025/06/05/general-dynamics-promotes-light-armoured-vehicles-at-cansec-as-controversial-export-to-saudi-arabia-continues/"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

INPUT_FILE = "./page_content.json"

MODEL_NAME = "gemini-2.0-flash-lite"

# TODO: refine
EXTRACTION_PROMPT = """
You are an information extraction system.
Your task is to extract specific fields from the provided article.
The topic is Canadian military exports/transactions.

Follow these rules strictly:
* Only include a field if you find a clear and unambiguous match. If the information is not explicitly present, omit that field entirely (do not use null, "", or placeholders).
* Do not copy entire paragraphs into a field. Summarize or extract only the relevant fragment directly answering the field’s requirement.
* Do not guess or infer — if the text is ambiguous, leave the field out.
* If a number is expected, provide only the numeric value (without units unless the unit is part of the field definition).
* Make sure all the data in each field is relevent to that field.
* try and fill out as many fields as you can accurately. Don't just put everything in the description, silly.

Fields to extract (omit if not found):
* "transaction_type": e.g. "Purchase Order", "Subcontract", etc. Do not give a long-winded description, just give the category the transaction belongs to.
* "company_division": Canadian company/division involved in the transaction
* "address_1", "address_2", "city", "province", "region", "postal_code": Address of the company
* "recipient": Recipient of the transaction, be it a country, organization, or individual
* "commodity_class": As specifically as you can possibly get, the product being traded in the transaction, e.g. missile components, avionics, engines
* "amount": Transaction amount, including the currency
* "description": Transaction description
* "source_date": Date in YYYY-MM-DD format the source/article was posted at.
* "source_description": Decription of the platform the source/article came from, as well as the content of the source/article.
* "grant_type": Type of grant
* "contract_number": Contract number
* "comments": Additional comments
* "is_primary": Boolean flag

---
ARTICLE TEXT:
{text_content}
"""

SCHEMA = {
  "type": "object",
  "required": ["source_description"],
  "properties": {
    "transaction_type": {"type": "string"},
    "company_division": {"type": "string"},
    "recipient": {"type": "string"},
    "amount": {"type": "number"},
    "description": {"type": "string"},
    "address_1": {"type": "string"},
    "address_2": {"type": "string"},
    "city": {"type": "string"},
    "province": {"type": "string"},
    "region": {"type": "string"},
    "postal_code": {"type": "string"},
    "source_date": {"type": "string"},
    "source_description": {"type": "string"},
    "grant_type": {"type": "string"},
    "commodity_class": {"type": "string"},
    "contract_number": {"type": "string"},
    "comments": {"type": "string"},
    "is_primary": {"type": "boolean"}
  }
}

def validate_info(extracted_info):
    if ("transaction_type" not in extracted_info):
        return False
    if (len(extracted_info["transaction_type"]) == 0):
        return False
    if ("company_division" not in extracted_info):
        return False
    if (len(extracted_info["company_division"]) == 0):
        return False
    if ("recipient" not in extracted_info):
        return False
    if (len(extracted_info["recipient"]) == 0):
        return False
    return True

def process_content_with_gemini(text_content):
    """
    Sends the text to the Gemini API with the extraction prompt and
    parses the JSON response.
    """
    model = genai.GenerativeModel(MODEL_NAME) # type: ignore
    prompt = EXTRACTION_PROMPT.format(text_content=text_content)

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_schema": SCHEMA,
                "response_mime_type": 'application/json',
            }
            )
        return json.loads(response.text)
    except Exception as e:
        print(f"   ❌ An error occurred while calling Gemini or parsing its response: {e}")
        return {"error": str(e)}


async def main():
    """Main function to run the data extraction process."""
    if not GOOGLE_API_KEY:
        print("❌ Error: GOOGLE_API_KEY environment variable not set.")
        return

    genai.configure(api_key=GOOGLE_API_KEY) # type: ignore

    scraped_page = await fetch_site(URL)
    if not scraped_page:
        print("❌ Error: No scraper results found.")
        return
    print(f"✅ FEED CONTENT: {scraped_page}")

    print(f"🤖 Starting information extraction with Gemini...")

    extracted_info = process_content_with_gemini(scraped_page)
    
    # Check if the extraction was successful and contains actual data
    if extracted_info and "error" not in extracted_info:
        print("   ✔️ Found relevant info")
        desc = ""
        if "source_description" in extracted_info:
            desc = extracted_info["source_description"]
        extracted_info["source_description"] = f"Sourced from Google Alerts. Url: {URL}. {desc}"
        for key, val in extracted_info.items():
            print(key, ":", val)
            print("---")
        return extracted_info

if __name__ == "__main__":
    asyncio.run(main())