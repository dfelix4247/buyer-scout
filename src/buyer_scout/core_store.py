from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

try:
    import scout_core  # noqa: F401  # dependency contract
except Exception:
    scout_core = None


BUYERS_COLUMNS = [
    "lead_id",
    "business_name",
    "website",
    "domain",
    "phone_primary",
    "phones_all",
    "customer_contact",
    "contact_role",
    "contact_email",
    "emails_all",
    "address_full",
    "years_in_business",
    "source_category",
    "source_url",
    "source_query",
    "provider",
    "enriched_at",
    "confidence",
    "notes",
]


@dataclass(slots=True)
class LeadRecord:
    business_name: str = ""
    website: str = ""
    domain: str = ""
    phone_primary: str = ""
    phones_all: str = ""
    customer_contact: str = ""
    contact_role: str = ""
    contact_email: str = ""
    emails_all: str = ""
    address_full: str = ""
    years_in_business: str = ""
    source_category: str = ""
    source_url: str = ""
    source_query: str = ""
    provider: str = ""
    confidence: str = ""
    notes: str = ""
    extras_json: str = ""


def record_to_dict(rec: Any) -> dict[str, Any]:
    if is_dataclass(rec) and not isinstance(rec, type):  # instance, not class
        return asdict(rec)

    if hasattr(rec, "model_dump") and callable(getattr(rec, "model_dump")):
        return rec.model_dump()

    if hasattr(rec, "dict") and callable(getattr(rec, "dict")):
        return rec.dict()

    if hasattr(rec, "__dict__"):
        return dict(rec.__dict__)

    raise TypeError(f"Unsupported record type for serialization: {type(rec)!r}")


class CoreStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS buyer_leads (
                    lead_id TEXT PRIMARY KEY,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    business_name TEXT,
                    website TEXT,
                    domain TEXT,
                    phone_primary TEXT,
                    phones_all TEXT,
                    customer_contact TEXT,
                    contact_role TEXT,
                    contact_email TEXT,
                    emails_all TEXT,
                    address_full TEXT,
                    years_in_business TEXT,
                    source_category TEXT,
                    source_url TEXT,
                    source_query TEXT,
                    provider TEXT,
                    enriched_at TEXT,
                    confidence TEXT,
                    notes TEXT,
                    extras_json TEXT
                )
                """
            )

    def _dedupe_key(self, rec: LeadRecord) -> str:
        if rec.domain:
            return f"domain:{rec.domain.lower()}"
        if rec.website:
            return f"website:{rec.website.lower()}"
        if rec.phone_primary:
            return f"phone:{''.join(ch for ch in rec.phone_primary if ch.isdigit())}"
        basis = f"{rec.business_name.lower()}|{rec.address_full.lower()}"
        return f"nameaddr:{hashlib.sha1(basis.encode('utf-8')).hexdigest()}"

    def upsert_lead(self, rec: LeadRecord) -> str:
        dedupe_key = self._dedupe_key(rec)
        lead_id = str(uuid5(NAMESPACE_URL, dedupe_key))
        enriched_at = datetime.now(timezone.utc).isoformat()

        rec_dict = record_to_dict(rec)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO buyer_leads (
                    lead_id, dedupe_key, business_name, website, domain, phone_primary, phones_all,
                    customer_contact, contact_role, contact_email, emails_all, address_full,
                    years_in_business, source_category, source_url, source_query, provider,
                    enriched_at, confidence, notes, extras_json
                ) VALUES (
                    :lead_id, :dedupe_key, :business_name, :website, :domain, :phone_primary, :phones_all,
                    :customer_contact, :contact_role, :contact_email, :emails_all, :address_full,
                    :years_in_business, :source_category, :source_url, :source_query, :provider,
                    :enriched_at, :confidence, :notes, :extras_json
                )
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    business_name=COALESCE(NULLIF(excluded.business_name,''), buyer_leads.business_name),
                    website=COALESCE(NULLIF(excluded.website,''), buyer_leads.website),
                    domain=COALESCE(NULLIF(excluded.domain,''), buyer_leads.domain),
                    phone_primary=COALESCE(NULLIF(excluded.phone_primary,''), buyer_leads.phone_primary),
                    phones_all=COALESCE(NULLIF(excluded.phones_all,''), buyer_leads.phones_all),
                    customer_contact=COALESCE(NULLIF(excluded.customer_contact,''), buyer_leads.customer_contact),
                    contact_role=COALESCE(NULLIF(excluded.contact_role,''), buyer_leads.contact_role),
                    contact_email=COALESCE(NULLIF(excluded.contact_email,''), buyer_leads.contact_email),
                    emails_all=COALESCE(NULLIF(excluded.emails_all,''), buyer_leads.emails_all),
                    address_full=COALESCE(NULLIF(excluded.address_full,''), buyer_leads.address_full),
                    years_in_business=COALESCE(NULLIF(excluded.years_in_business,''), buyer_leads.years_in_business),
                    source_category=excluded.source_category,
                    source_url=COALESCE(NULLIF(excluded.source_url,''), buyer_leads.source_url),
                    source_query=COALESCE(NULLIF(excluded.source_query,''), buyer_leads.source_query),
                    provider=excluded.provider,
                    enriched_at=excluded.enriched_at,
                    confidence=COALESCE(NULLIF(excluded.confidence,''), buyer_leads.confidence),
                    notes=COALESCE(NULLIF(excluded.notes,''), buyer_leads.notes),
                    extras_json=COALESCE(NULLIF(excluded.extras_json,''), buyer_leads.extras_json)
                """,
                {
                    "lead_id": lead_id,
                    "dedupe_key": dedupe_key,
                    "enriched_at": enriched_at,
                    **rec_dict,
                },
            )
        return lead_id

    def export_buyers_csv(self, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT lead_id, business_name, website, domain, phone_primary, phones_all, "
                "customer_contact, contact_role, contact_email, emails_all, address_full, "
                "years_in_business, source_category, source_url, source_query, provider, "
                "enriched_at, confidence, notes FROM buyer_leads ORDER BY business_name, lead_id"
            ).fetchall()

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=BUYERS_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row[k] or "" for k in BUYERS_COLUMNS})

    def to_json(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)
