# 10-K Item 7 Extractor & Sentiment Analyser

> **Status:** Work in progress. Stage 1 (extraction) is functional. Stage 2 (LLM-based sentiment & tone analysis) is in active development.

## What this project does

This project builds a data pipeline that pulls **Item 7 — Management's Discussion and Analysis (MD&A)** out of a public company's 10-K annual report on SEC EDGAR, cleans the text, and feeds it into Anthropic's Claude API for **sentiment and tone analysis** across multiple years of filings for the same company.

The end goal is to be able to answer questions like:
- *Has Apple's management commentary become more cautious or more confident year over year?*
- *How does the tone of one company's MD&A compare to a competitor's in the same fiscal year?*

Item 7 is a particularly interesting section to analyse because it's where management explains, in their own words, how the business performed and what risks and opportunities they see ahead. That makes it a rich source of qualitative signal that complements the hard numbers elsewhere in the 10-K.

## Why I'm building this

I'm an aspiring Data Analyst, and this project is part of my portfolio. I'm using it to learn:

- Working with publicly available APIs (SEC EDGAR)
- Working with an LLM API (Anthropic / Claude)
- Practical use of core Python libraries — `requests`, `beautifulsoup4`, `re`, `pandas`
- Real-world data extraction from messy, unstructured HTML
- Designing an end-to-end data pipeline from extraction → cleaning → analysis

## Pipeline overview

```
  Ticker (e.g. "AAPL")
        │
        ▼
  ┌──────────────────────────┐
  │ 1. Ticker → CIK lookup   │   SEC company tickers JSON
  └──────────────────────────┘
        │
        ▼
  ┌──────────────────────────┐
  │ 2. Filing discovery      │   data.sec.gov submissions API
  │    (recent 10-Ks)        │
  └──────────────────────────┘
        │
        ▼
  ┌──────────────────────────┐
  │ 3. Download 10-K HTML    │   www.sec.gov/Archives/...
  └──────────────────────────┘
        │
        ▼
  ┌──────────────────────────┐
  │ 4. Extract Item 7 (MD&A) │   BeautifulSoup + regex
  └──────────────────────────┘
        │
        ▼
  ┌──────────────────────────┐
  │ 5. Sentiment & tone      │   Anthropic API
  │    analysis              │
  └──────────────────────────┘
        │
        ▼
  ┌──────────────────────────┐
  │ 6. Visualisation of      │   ◀── in progress
  │    results               │
  └──────────────────────────┘
        │
        ▼
  pandas DataFrame: one row per filing,
  with extracted text + analysis results
```

## Where I'm currently up to

**Done**
- Ticker → CIK resolution against the SEC company tickers file
- Discovery of the most recent N 10-K filings for a given CIK
- Downloading the raw filing HTML with the headers and rate limits SEC requires
- Parsing the HTML with BeautifulSoup and isolating Item 7 between the *"Item 7. Management's Discussion"* and *"Item 7A. Quantitative..."* boundaries with regex
- Skipping the table-of-contents match by taking the second occurrence of the start pattern
- Storing results in a pandas DataFrame with metadata (ticker, CIK, filing date, fiscal year end, accession number, extracted text, word count)
- Connected the Anthropic API, fed the extracted Item 7 text into Claude, and received a structured JSON response with sentiment and tone scores
- Authored dedicated `SYSTEM` and `USER` prompt templates in `prompts.py` to guide the LLM's analysis

**In progress**
- Storing the JSON response from the LLM in a local data file so I don't need to re-call the API on every run
- Building a visualisation chart to display the analysis results for a single company across years

**Planned next**
- Once the single-company visualisation is working as intended, run the analysis across multiple companies and chart them together for comparison
- Once cross-company charting is working, refactor the pipeline to accept a **list of companies** as input rather than a single ticker

## Tech stack

- **Python 3**
- `requests` — HTTP calls to SEC
- `beautifulsoup4` + `lxml` — HTML parsing
- `pandas` — tabular storage of extracted filings
- `python-dotenv` — managing secrets (SEC user email, API keys)
- `anthropic` — Claude API for sentiment/tone analysis
- `json` — persisting LLM analysis output to disk
- `matplotlib` *(coming next)* — visualising sentiment and tone trends across years

## How to run

1. Clone the repo and install dependencies:

   ```bash
   pip install requests beautifulsoup4 lxml pandas python-dotenv
   ```

2. Copy `.env.example` to `.env` and fill in your Anthropic API key and contact email — SEC requires every request to identify the requester:

   ```
   ANTHROPIC_API_KEY=your-api-key
   SEC_USER_EMAIL=your.name@example.com
   ```

3. Run the script:

   ```bash
   python edgar_item7.py
   ```

   By default it pulls the 3 most recent 10-Ks for Apple (`AAPL`), extracts Item 7 from each, and prints a summary plus a preview of the most recent MD&A.

## Notes on working with SEC EDGAR

A few things I've learned from this project that aren't obvious until you start hitting the API:

- **SEC requires a `User-Agent` header** identifying the requester, otherwise it returns 403. The script reads the email from `.env` and includes it in every request.
- **Rate limit is 10 requests/second.** The script sleeps `0.2s` between filings to stay well under that.
- **Two subdomains**: `www.sec.gov` serves filing documents, `data.sec.gov` serves JSON metadata.
- **10-K HTML has no semantic markup** for Item 7 — there's no `<section id="item-7">` to grab. Locating the section means matching heading text in regex, and being careful to skip the table-of-contents reference at the top of the document.

## Repository structure

```
edgar_item7.py    # Main script — extraction, LLM analysis, and persistence
prompts.py        # System and user prompt templates for the Anthropic API
data/             # Saved LLM JSON responses, one file per ticker (e.g. AAPL.json)
CLAUDE.md         # Working notes / project context
README.md         # This file
.env.example      # Template for required environment variables
.env              # SEC_USER_EMAIL and ANTHROPIC_API_KEY (not committed)
```
