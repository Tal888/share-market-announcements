# EDGAR Item 7 Extractor

## Project Overview

This is a Python script (`edgar_item7.py`) that programmatically extracts **Item 7 (Management's Discussion and Analysis, or MD&A)** from a company's 10-K annual report filings on SEC EDGAR. The extracted text is stored in a pandas DataFrame for downstream analysis.

The end goal is to enable **sentiment analysis and tone comparison** of MD&A sections across multiple years and companies — for example, comparing how Apple's management commentary has shifted year over year, or comparing the tone of MD&A between competitors.

## What the Script Does

The pipeline has four stages:

1. **Ticker → CIK lookup**: Converts a stock ticker (e.g., "AAPL") into SEC's Central Index Key (CIK) using EDGAR's company tickers JSON file.
2. **Filing discovery**: Queries SEC's submissions API at `data.sec.gov` to get a list of recent 10-K filings for that CIK.
3. **Document download**: Fetches the raw HTML of each 10-K from `www.sec.gov/Archives/...`.
4. **Item 7 extraction**: Parses the HTML with BeautifulSoup, locates Item 7 boundaries using regex (between "Item 7. Management's Discussion" and "Item 7A. Quantitative..."), and extracts the section text.

The final output is a pandas DataFrame with one row per filing, containing the ticker, CIK, filing date, fiscal year end, accession number, extracted Item 7 text, and word count.

## Key Technical Details

- **SEC rate limit**: Maximum 10 requests per second. The script uses `time.sleep(0.2)` between filings to stay under this.
- **Required headers**: SEC blocks requests without a proper `User-Agent` header (must include name and email). `Accept-Encoding: gzip, deflate` is also recommended for bandwidth efficiency.
- **Two SEC subdomains used**: `www.sec.gov` for filing documents, `data.sec.gov` for JSON metadata.
- **Parsing challenge**: 10-K HTML has no semantic markup identifying Item 7. The script uses regex to find heading text, and skips the table of contents by taking the **second** match of the start pattern (the first match is the TOC entry).

## Dependencies

- `requests` — HTTP requests to SEC
- `beautifulsoup4` + `lxml` — HTML parsing
- `pandas` — DataFrame storage
- `python-dotenv` — load secrets from `.env` (SEC contact email, Anthropic API key)
- `anthropic` — Claude API client for sentiment/tone analysis
- `os`, `re`, `time`, `warnings` — standard library

## How to Run

```bash
python edgar_item7.py
```

The script's `__main__` block is configured to pull the 3 most recent 10-Ks for Apple (AAPL) and print a summary plus a preview of the most recent Item 7.

## Common Issues I'm Looking For Help With

When debugging errors, please consider these likely failure modes:

1. **HTTP errors (403, 429)**: Usually indicate SEC has blocked the request — typically due to a missing/malformed User-Agent header or exceeding rate limits.
2. **Regex extraction failures**: The "Could not locate Item 7 boundaries" error happens when the regex patterns don't find both a start and end match. This often happens with older filings, smaller reporting companies, or unusual HTML formatting.
3. **Parallel array indexing issues**: SEC returns filing metadata as parallel arrays (`recent["form"]`, `recent["accessionNumber"]`, etc.) — bugs can arise if these arrays aren't iterated correctly with matching indices.
4. **Encoding issues**: Some filings contain Unicode characters (curly quotes, em dashes) that can cause regex matching problems if not handled with the right character classes.
5. **Empty or truncated extractions**: If Item 7 comes out unexpectedly short, the regex might be matching the TOC entry instead of the real section, or the end pattern might be matching too early.

## What I'm Trying to Learn

I'm building this project to learn:
- Web scraping and API consumption with proper rate limiting
- HTML parsing with BeautifulSoup
- Regex pattern construction for messy real-world text
- Pandas DataFrame workflows
- Best practices for working with public APIs (SEC EDGAR specifically)
- Python Skills that will be valuable for a Data Analyst resume
- I'm also building this project to put on my portfolio on GitHub for when I apply for new Data Analyst related roles.

When helping with errors, please **explain the underlying cause** rather than just providing a fix — I want to understand *why* something went wrong, not just make the error go away.

When helping with writing new code, please **outline the components needed to code the new feature** rather than just providing me the answer - I want to practise writing code and critically think about why I'm writing it. Help guide me in the right direction.

## File Structure

```
edgar_item7.py          # Main script
prompts.py              # System and user prompt templates for the Anthropic API
CLAUDE.md               # This file - project context
README.md               # Project overview and run instructions
.env.example            # Template for required env vars (copy to .env)
.env                    # Local secrets (not committed)
```
