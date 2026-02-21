from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

from buyer_scout.commands.export import run_export
from buyer_scout.core_store import CoreStore, LeadRecord
from buyer_scout.parsers.bbb_profile_parser import parse_bbb_profile
from buyer_scout.providers.bbb_browser import BBBBrowser


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def run_crawl_bbb(
    store: CoreStore,
    browser: BBBBrowser,
    query: str,
    location: str,
    max_results: int,
    out_csv: Path,
    debug: bool = False,
    profile_path: Path | None = None,
) -> None:
    try:
        listings = browser.collect_results(query=query, location=location, max_results=max_results)
    except Exception:
        if browser.debug_dir:
            browser.debug_url("https://www.bbb.org/", browser.debug_dir / "results")
        raise

    for listing in listings[:max_results]:
        artifact_dir = None
        if debug and browser.debug_dir:
            safe = listing["url"].split("/")[-1].replace("?", "_")
            artifact_dir = browser.debug_dir / "profiles" / safe

        session = browser.scrape_profile(url=listing["url"], artifact_dir=artifact_dir)
        try:
            parsed = parse_bbb_profile(session["page"], listing["url"], profile_path=profile_path)
            website = parsed.get("website", "")
            source_query = json.dumps({"query": query, "location": location}, sort_keys=True)
            extras = {
                "selector_log": parsed.get("selector_log", {}),
                "search_term": query,
                "listing_name": listing.get("name", ""),
                "console_messages": session.get("console", []),
                "network_count": len(session.get("network", [])),
            }
            extras.update(parsed.get("extra_fields", {}))
            lead_id = store.upsert_lead(
                LeadRecord(
                    business_name=parsed.get("business_name", ""),
                    website=website,
                    domain=_domain(website),
                    phone_primary=parsed.get("phone_primary", ""),
                    phones_all=parsed.get("phones_all", ""),
                    customer_contact=parsed.get("customer_contact", ""),
                    address_full=parsed.get("address_full", ""),
                    years_in_business=parsed.get("years_in_business", ""),
                    source_category="bbb",
                    source_url=listing["url"],
                    source_query=source_query,
                    provider="bbb_playwright",
                    extras_json=store.to_json(extras),
                )
            )
            if debug and browser.debug_dir and artifact_dir:
                debug_target = browser.debug_dir / "profiles" / lead_id
                debug_target.mkdir(parents=True, exist_ok=True)
                for file_name in ("page.html", "screenshot.png"):
                    src = artifact_dir / file_name
                    if src.exists():
                        src.replace(debug_target / file_name)
        finally:
            browser.close_scrape_session(session)
        time.sleep(0.8)

    run_export(store, out_csv)
