from __future__ import annotations

from pathlib import Path

from buyer_scout.commands.export import run_export
from buyer_scout.core_store import CoreStore, LeadRecord
from buyer_scout.providers.serpapi_provider import SerpAPIProvider


def run_discover_serp(store: CoreStore, query: str, max_results: int, out_csv: Path) -> None:
    provider = SerpAPIProvider()
    results = provider.search(query=query, max_results=max_results)

    for item in results:
        extras = store.to_json({"rank": item.get("position", ""), "snippet": item.get("snippet", "")})
        store.upsert_lead(
            LeadRecord(
                business_name=item.get("business_name", ""),
                website=item.get("website", ""),
                domain=item.get("domain", ""),
                phone_primary=item.get("phone_primary", ""),
                phones_all=item.get("phones_all", ""),
                contact_email=item.get("contact_email", ""),
                emails_all=item.get("emails_all", ""),
                source_category="serpapi",
                source_url=item.get("source_url", ""),
                source_query=query,
                provider="serpapi",
                extras_json=extras,
            )
        )

    run_export(store, out_csv)
