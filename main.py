import asyncio
from pprint import pprint
from typing import Optional
import google.generativeai as genai
import json
import os
import re
import time
from dotenv import load_dotenv
import requests

from fetch_site import fetch_site
load_dotenv()

URL = "https://pbicanada.org/2025/06/05/general-dynamics-promotes-light-armoured-vehicles-at-cansec-as-controversial-export-to-saudi-arabia-continues/"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

MODEL_NAME = "gemini-2.0-flash-lite"

# TODO: refine
EXTRACTION_PROMPT = """
You are a precise data-extraction system.

Given the DOCUMENT TEXT below, extract ALL transactions or arms-export relevant
entries and output a JSON array (possibly empty) of objects that match the
Project Ploughshares API schema. Output ONLY the JSON array — no markdown,
no commentary, no code fences.

Each object must use the following fields (required fields must be provided
and set to "Not Found" if absent):

Required fields:
- transaction_type (string)          # e.g., "Export", "Purchase Order", "Component Supply"
- company_division (string)          # company or division name (use "Not Found" if unknown)
- recipient (string)                 # receiving country or recipient (use "Not Found" if unknown)

Optional fields (include if present):
- amount (string or number)          # monetary value if present (e.g., "15,000,000 CAD")
- description (string)
- address_1, address_2, city, province, region, postal_code
- source_date (string YYYY-MM-DD)
- source_description (string)
- grant_type (string)
- commodity_class (string)           # e.g., missile components, avionics, engines
- contract_number (string)
- comments (string)
- is_primary (boolean)

Additionally, include these two new fields to help filter relevance:
- canadian_relevance (string)        # one of: "direct", "indirect", "none"
  - "direct" = Canadian company or Canada-origin export of military goods/components
  - "indirect" = Canadian-made parts/components appear in a larger export (final assembly elsewhere)
  - "none" = no meaningful Canadian connection
- relation_explanation (string)      # short explanation why this is direct/indirect/none (1-2 sentences)

Rules:
1. If a piece of info cannot be found, set it to the string "Not Found" (not null).
2. If multiple transactions are described in the text, output them as separate objects.
3. If the text contains the same transaction repeated, ensure you only output one object per distinct transaction.
4. Output must be valid JSON (an array). Example:
   [
     {{
       "transaction_type": "Export",
       "company_division": "Example Corp Canada",
       "recipient": "Country X",
       "amount": "3,000,000 CAD",
       "commodity_class": "avionics modules",
       "description": "Example summary ...",
       "source_url": "https://example.com/article",
       "canadian_relevance": "direct",
       "relation_explanation": "Company is based in Canada and shipped avionics modules."
     }}
   ]

DOCUMENT TEXT:
{text_content}
"""

def extract_json_from_text(text):
    """
    Attempts to find and return the first JSON array or object in a text blob.
    This removes markdown fences and extracts from the first '[' ... ']' or '{' ... '}' pair.
    """
    if not text or not isinstance(text, str):
        return None
    # remove common fences
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # Try to locate a JSON array first
    arr_match = re.search(r"(\[.*\])", cleaned, flags=re.DOTALL)
    if arr_match:
        return arr_match.group(1)

    # Otherwise try a single JSON object
    obj_match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
    if obj_match:
        return obj_match.group(1)

    return None

def process_content_with_gemini(text_content):
    """
    Sends the text to Gemini with the extraction prompt and parses the JSON response.
    Uses your existing SDK usage pattern (genai.GenerativeModel).
    """
    # Keep using your existing model init pattern
    model = genai.GenerativeModel(MODEL_NAME) # type: ignore

    prompt = EXTRACTION_PROMPT.format(text_content=text_content)

    try:
        # Generate content. Your original code used model.generate_content(prompt)
        response = model.generate_content(prompt)
        # Response object in your environment exposes .text (as in your original script)
        raw = getattr(response, "text", str(response))
        # Try to extract JSON from the possibly noisy response
        json_fragment = extract_json_from_text(raw) or raw

        # Parse JSON
        parsed = json.loads(json_fragment)
        # Ensure it's an array
        if isinstance(parsed, dict):
            parsed = [parsed]
        return parsed

    except Exception as e:
        print(f"   ❌ An error occurred while calling Gemini or parsing its response: {e}")
        # print raw text to help debugging if available
        try:
            print("   Raw response (truncated):", raw[:1000])
        except Exception:
            pass
        return {"error": str(e)}

def is_valid_transaction(tx):
    """
    Basic validation to ensure required API fields exist.
    Required fields (per API): transaction_type, company_division, recipient
    If a field is present but "Not Found", treat as missing for the
    purposes of deciding whether to keep the record (we still surface it sometimes).
    """
    for field in ["transaction_type", "company_division", "recipient"]:
        if field not in tx or not tx[field] or tx[field] == "Not Found":
            return False
    return True

API_BASE_URL = "http://ploughshares.nixc.us/api/transaction"
HEADERS = {"Content-Type": "application/json"}

allowed_fields = {
    "transaction_type", "company_division", "recipient", "amount",
    "description", "address_1", "address_2", "city", "province", "region",
    "postal_code", "source_date", "source_description", "grant_type",
    "commodity_class", "contract_number", "comments", "is_primary"
}

def clean_for_api(tx):
    cleaned = {k: v for k, v in tx.items() if k in allowed_fields}

    # Remove invalid source_date
    if "source_date" in cleaned:
        if not isinstance(cleaned["source_date"], str) or cleaned["source_date"].lower() == "not found":
            cleaned.pop("source_date")

    # Remove invalid amount (API expects numeric)
    if "amount" in cleaned:
        # If "Not Found" or not parseable as a float, drop it
        try:
            float(str(cleaned["amount"]).replace(",", "").replace("$", ""))
        except ValueError:
            cleaned.pop("amount")

    # Use source_url for source_description
    if "source_url" in tx:
        cleaned["source_description"] = tx["source_url"]

    return cleaned


def post_transaction(transaction):
    payload = clean_for_api(transaction)
    response = requests.post(API_BASE_URL, headers=HEADERS, json=payload)
    if response.status_code == 200 or response.status_code == 201:
        print(f"✅ Created transaction for {payload['company_division']} → ID: {response.json().get('transaction_id')}")
    else:
        print(f"❌ Failed to create transaction: {response.status_code} - {response.text}")

async def main():
    """Main function to run the data extraction process."""
    if not GOOGLE_API_KEY:
        print("❌ Error: GOOGLE_API_KEY environment variable not set.")
        return

    genai.configure(api_key=GOOGLE_API_KEY) # type: ignore

    print("Retrieving all feed contents...")
    scraped_page = await fetch_site(URL)
    if not scraped_page:
        print("❌ Error: No results found.")
        return
    print("✅ Successfully retrieved content.")

    print(f"🤖 Starting information extraction with Gemini...")

    # Avoid processing pages with very little text
    text = scraped_page
    if len(text) < 150:
        print("   ⏩ Skipping page due to insufficient content.")
        return

    extracted_items = process_content_with_gemini(scraped_page)
    
    # If model returned a single object or error, handle gracefully
    if not extracted_items:
        print("   ⚪ Gemini returned no items.")
        time.sleep(1)
        return
    if isinstance(extracted_items, dict) and "error" in extracted_items:
        print("   ⚠️ Gemini error:", extracted_items.get("error"))
        time.sleep(1)
        return

    # iterate through items (should be array of objects)
    for tx in extracted_items:
        # attach source_url for traceability
        tx.setdefault("source_url", URL) # type: ignore

        # if the model gives canadian_relevance, use it to decide whether to keep
        relevance = (tx.get("canadian_relevance") or "none").lower() # type: ignore
        explanation = tx.get("relation_explanation", "") # type: ignore

        # If model says 'none', skip by default (these are the irrelevant ones like US missile contracts)
        if relevance == "none":
            print("   ⚪ Skipping — model marked this as non-Canadian. Explanation:", explanation[:200])
            continue

        # basic required-field check (we want the API-required fields present)
        if not is_valid_transaction(tx):
            print("   ⚠️ Skipping — missing required API fields in extracted transaction:", tx)
            continue

        # Optionally normalize some fields (convert "amount" to a canonical string) - keep simple for now
        # Save the item
        pprint(tx)
        print("---")

if __name__ == "__main__":
    asyncio.run(main())