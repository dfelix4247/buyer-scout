# buyer-scout

Python 3.12 CLI for buyer lead acquisition from:
- BBB authenticated crawl via Playwright
- Google discovery via SerpAPI

Both pipelines write to the same SQLite DB and export a unified `./data/buyers.csv`.

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ..\scout-core
pip install -e .
pip install playwright
python -m playwright install
```

## Environment variables

- `SCOUT_DB_PATH` (default: `C:\Users\danie\dev\scout-data\scout.db`)
- `BUYER_SCOUT_AUTH_PATH` (default: `C:\Users\danie\dev\scout-data\buyer-scout\auth.json`)
- `BUYER_SCOUT_DEBUG_DIR` (default: `C:\Users\danie\dev\scout-data\buyer-scout\debug`)
- `SERPAPI_API_KEY` (required for `discover-serp`)

## Commands

Auth once:

```powershell
buyer-scout auth-bbb
```

Crawl BBB:

```powershell
buyer-scout crawl-bbb --query "Real Estate Investors" --location "Los Angeles, CA" --max 25
```

SerpAPI discovery:

```powershell
buyer-scout discover-serp --query "we buy houses cash Los Angeles" --max 25
```

Export only:

```powershell
buyer-scout export --out ./data/buyers.csv
```

Debug selectors:

```powershell
buyer-scout debug-bbb --url "https://www.bbb.org/us/..." --headed --slowmo-ms 250
```

## Selector-stability checklist

Recommended selector strategy:
- Prefer `get_by_role()` / ARIA roles and labeled controls over CSS classes.
- Anchor extraction on visible labels (for example `Phone Number` then adjacent value).
- Use multiple fallbacks in order: role/label → data-* attribute → stable text patterns → minimal CSS selectors.
- Avoid brittle selectors: long CSS chains, generated class names, `nth-child` selectors.
- Wait for a stable container (results list/profile header) before extraction.
- Always timebox (explicit timeouts + 1-2 retries, then skip).

Debug workflow:
1. Run `buyer-scout auth-bbb` to refresh a valid login session.
2. Run `buyer-scout debug-bbb --headed --slowmo-ms 250 --url <target>`.
3. Inspect artifacts in `BUYER_SCOUT_DEBUG_DIR` (`page.html`, `screenshot.png`, `console.log`, `network.json`, `meta.json`).
4. Update parser selectors in `src/buyer_scout/parsers/bbb_profile_parser.py`.
5. Re-run `debug-bbb` on the same URL before scaling with `crawl-bbb`.

Logging guidance:
- Keep selector-path logs per field (example: `phone: label_fallback_2`).
- On extraction failure include URL + field + error class.

## Output schema

`./data/buyers.csv` includes:

- `lead_id`
- `business_name`
- `website`
- `domain`
- `phone_primary`
- `phones_all`
- `customer_contact`
- `contact_role`
- `contact_email`
- `emails_all`
- `address_full`
- `years_in_business`
- `source_category`
- `source_url`
- `source_query`
- `provider`
- `enriched_at`
- `confidence`
- `notes`

Each command exports `./data/buyers.csv` after writing data.
