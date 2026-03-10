from __future__ import annotations

import json
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
    timeout_sec: int = 60,
) -> None:
    listings = browser.collect_results(
        query=query,
        location=location,
        max_results=max_results,
        timeout_sec=timeout_sec,
    )

    if not listings:
        raise RuntimeError("crawl-bbb found no listings; see debug artifacts and auth state")

    print(f"Collected {len(listings)} BBB profile listing URL(s)")

    for idx, listing in enumerate(listings[:max_results], start=1):
        artifact_dir = None
        if debug and browser.debug_dir:
            safe = listing["url"].split("/")[-1].replace("?", "_")
            artifact_dir = browser.debug_dir / "profiles" / f"{idx:03d}-{safe}"

        session = browser.scrape_profile(url=listing["url"], artifact_dir=artifact_dir, timeout_sec=timeout_sec)
        try:
            parsed = parse_bbb_profile(session["page"], listing["url"], profile_path=profile_path)
            website = parsed.get("website", "")
            source_query = json.dumps({"query": query, "location": location}, sort_keys=True)
            extras = {
                "selector_log": parsed.get("selector_log", {}),
                "search_term": query,
                "search_location": location,
                "listing_name": listing.get("name", ""),
                "console_messages": session.get("console", []),
                "network_count": len(session.get("network", [])),
                "business_started": parsed.get("business_started", ""),
                "principal_contact": parsed.get("principal_contact", ""),
            }
            extras.update(parsed.get("extra_fields", {}))
            lead_id = store.upsert_lead(
                LeadRecord(
                    business_name=parsed.get("business_name", ""),
                    website=website,
                    domain=_domain(website),
                    phone_primary=parsed.get("phone_primary", ""),
                    phones_all=parsed.get("phones_all", ""),
                    customer_contact=parsed.get("customer_contact", "") or parsed.get("principal_contact", ""),
                    address_full=parsed.get("address_full", ""),
                    years_in_business=parsed.get("years_in_business", "") or parsed.get("business_started", ""),
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

    run_export(store, out_csv)
