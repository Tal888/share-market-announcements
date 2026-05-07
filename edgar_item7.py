"""
Extract Item 7 (MD&A) from a company's 10-K filing on SEC EDGAR.
Stores the result in a pandas DataFrame.
"""

import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
import warnings
from bs4 import XMLParsedAsHTMLWarning
import json
from pathlib import Path


# Load env variables and create API client for later use
from dotenv import load_dotenv
from anthropic import Anthropic
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

load_dotenv()

def require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"{var_name} not found in .env file. Copy .env.example into .env and fill in key and email values.")
    return value

ANTHROPIC_API_KEY = require_env("ANTHROPIC_API_KEY")
SEC_USER_EMAIL = require_env("SEC_USER_EMAIL")

client = Anthropic(api_key=ANTHROPIC_API_KEY)


# SEC requires a User-Agent header identifying the requester.
HEADERS = {
    "User-Agent": f"Portfolio Project {SEC_USER_EMAIL}",
    "Accept-Encoding": "gzip, deflate"
}

# SEC 10-K filings are Inline XBRL (HTML with embedded XML namespaces).
# The HTML parser is correct here; suppress the misleading warning.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def get_cik_from_ticker(ticker: str) -> str:
    """Look up a company's CIK number from its ticker symbol."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker_upper:
            # CIK must be zero-padded to 10 digits for the submissions API
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker {ticker} not found in EDGAR")


def get_10k_filings(cik: str, limit: int = 3) -> list[dict]:
    """Get a list of recent 10-K filings for a given CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    recent = data["filings"]["recent"]
    filings = []
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            filings.append({
                "accession_number": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
                "primary_document": recent["primaryDocument"][i],
            })
            if len(filings) >= limit:
                break
    return filings


def fetch_10k_document(cik: str, accession_number: str, primary_document: str) -> str:
    """Download the raw HTML of a 10-K filing."""
    accession_clean = accession_number.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession_clean}/{primary_document}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    print(f"URL = {url}")
    return resp.text


def extract_item_7(html: str) -> str:
    """
    Extract the text of Item 7 (MD&A) from a 10-K HTML document.

    Strategy: convert HTML to clean text, then locate the boundaries of
    Item 7 using regex patterns. Item 7 ends at Item 7A (Quantitative and
    Qualitative Disclosures About Market Risk).
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove scripts, styles, and hidden elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Get clean text with reasonable spacing
    text = soup.get_text(separator="\n")

    # Normalize whitespace: collapse multiple blank lines and spaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)

    # Build regexes to find Item 7 start and Item 7A start (the end boundary).
    # Filings vary: "ITEM 7.", "Item 7 -", "Item 7:", with varying whitespace.
    # We require the section heading to appear on its own line or near one,
    # and we look for the SECOND occurrence to skip the table of contents.
    start_pattern = re.compile(
        r"item\s*7\s*[\.\-:]?\s*management['\u2019]s\s+discussion",
        re.IGNORECASE,
    )
    end_pattern = re.compile(
        r"item\s*7a\s*[\.\-:]?\s*quantitative",
        re.IGNORECASE,
    )

    start_matches = list(start_pattern.finditer(text))
    end_matches = list(end_pattern.finditer(text))

    if not start_matches or not end_matches:
        raise ValueError("Could not locate Item 7 boundaries in document")

    # Skip the table of contents: take the second match if available.
    # The TOC entry and the actual section heading look the same textually,
    # but the TOC is near the top of the document.
    start_idx = start_matches[1].start() if len(start_matches) >= 2 else start_matches[0].start()
    end_idx = end_matches[1].start() if len(end_matches) >= 2 else end_matches[0].start()

    if end_idx <= start_idx:
        # Fall back: find the first end match after start
        end_candidates = [m.start() for m in end_matches if m.start() > start_idx]
        if not end_candidates:
            raise ValueError("Item 7A (end boundary) not found after Item 7")
        end_idx = end_candidates[0]

    item_7_text = text[start_idx:end_idx].strip()
    return item_7_text


def build_item7_dataframe(ticker: str, num_filings: int = 3) -> pd.DataFrame:
    """Main pipeline: get N most recent 10-Ks for a ticker and extract Item 7."""
    cik = get_cik_from_ticker(ticker)
    print(f"CIK for {ticker}: {cik}")

    filings = get_10k_filings(cik, limit=num_filings)
    print(f"Found {len(filings)} 10-K filings")

    rows = []
    for filing in filings:
        print(f"  Processing {filing['filing_date']} (FY {filing['report_date']})...")
        try:
            html = fetch_10k_document(cik, filing["accession_number"], filing["primary_document"])
            item_7 = extract_item_7(html)
            rows.append({
                "ticker": ticker.upper(),
                "cik": cik,
                "filing_date": filing["filing_date"],
                "fiscal_year_end": filing["report_date"],
                "accession_number": filing["accession_number"],
                "item_7_text": item_7,
                "item_7_word_count": len(item_7.split()),
            })
        except Exception as e:
            print(f"    Error: {e}")
            rows.append({
                "ticker": ticker.upper(),
                "cik": cik,
                "filing_date": filing["filing_date"],
                "fiscal_year_end": filing["report_date"],
                "accession_number": filing["accession_number"],
                "item_7_text": None,
                "item_7_word_count": None,
            })
        # SEC rate limit: max 10 requests/second. Sleep to be polite.
        time.sleep(0.2)

    return pd.DataFrame(rows)

def combine_item_7(df: pd.DataFrame) -> str:
    # Check if any extracted item 7 texts are empty and raise an error with corresponding years if applicable 
    if df["item_7_text"].isna().any():
        empty_years = df.loc[df["item_7_text"].isna()]["fiscal_year_end"].str[:4].tolist()
        raise ValueError(f"Empty Item 7 Years: {', '.join(empty_years)}")

    final_text = []
    for i in range(len(df)):
        year = df["fiscal_year_end"].iloc[i][:4]
        text = df["item_7_text"].iloc[i]
        final_text.append(f"<Start of {year}>{text}<End of {year}>")
    chronological_text = final_text[::-1]
    return "".join(chronological_text)

def get_analysis(
    user_message: str,
    system: str = SYSTEM_PROMPT,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 8192
) -> dict:
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message},
                  {"role": "assistant", "content": "```json"}],
        stop_sequences=["```"]
    )
    raw_text = message.content[0].text
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw response was:\n{raw_text}")
        raise

def save_analysis(response_json: dict, ticker: str):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    with open(data_dir / f"{ticker}.json", "w") as f:
        json.dump(response_json, f, indent=2)

def main():
    # Customisable Company Ticker and Number of Filings
    ticker = "AAPL"
    num_filings = 5

    df = build_item7_dataframe(ticker=ticker, num_filings=num_filings)
    item_7_text = combine_item_7(df)
    user_message = USER_PROMPT_TEMPLATE.replace("{item_7_text}", item_7_text)
    system = SYSTEM_PROMPT

    # Customisable Model Parameters
    model = "claude-haiku-4-5-20251001"
    max_tokens = 8192

    num_tokens = client.messages.count_tokens(
        model=model,
        system=system,
        messages=[{"role": "user", "content": user_message}]
        )
    print(f"Number of Input Tokens = {num_tokens.input_tokens}")
    results = get_analysis(user_message=user_message, system=system, model=model, max_tokens=max_tokens)

    print(json.dumps(results, indent=2))

    #print(f"Length of Combined Item 7 = {len(user_message.split())}")
    #print(f"df['item_7_text'][0] looks like:\n{df['item_7_text'][0]}")
    #print(f"Fiscal Year:\n{df['fiscal_year_end'].iloc[0][:4]}")

    # Show summary (truncate the long text column for display)
    #summary = df.drop(columns=["item_7_text"]).copy()
    #print("\n=== Summary ===")
    #print(summary.to_string())

    # Show a preview of one Item 7
    #print("\n=== Preview of most recent Item 7 (first 800 chars) ===")
    #if df.iloc[0]["item_7_text"]:
    #    print(df.iloc[0]["item_7_text"][:800])


if __name__ == "__main__":
    main()