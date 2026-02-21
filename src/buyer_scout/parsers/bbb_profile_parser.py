from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "bbb_default.json"

KNOWN_RECORD_FIELDS = {
    "business_name",
    "website",
    "phone_primary",
    "phones_all",
    "years_in_business",
    "customer_contact",
    "address_full",
}


def _value_next_to_label(page: Page, label: str, prefer_href: bool = False) -> str:
    label_loc = page.get_by_text(label, exact=False).first
    if label_loc.count() == 0:
        return ""
    candidate = label_loc.locator("xpath=following::*[self::a or self::p or self::span or self::div][1]")
    if candidate.count() == 0:
        return ""
    first = candidate.first
    if prefer_href:
        href = first.get_attribute("href")
        if href:
            return href.strip()
    return first.inner_text().strip()


def _first_text(locators: list[Locator]) -> str:
    for locator in locators:
        if locator.count() > 0:
            txt = locator.first.inner_text().strip()
            if txt:
                return txt
    return ""


def _load_profile(profile_path: Path | None) -> dict[str, Any]:
    resolved = profile_path or DEFAULT_PROFILE_PATH
    return json.loads(resolved.read_text(encoding="utf-8"))


def _extract_from_spec(page: Page, spec: dict[str, Any]) -> tuple[str, str]:
    strategy = spec.get("strategy", "")
    selector_hint = "missing"

    if strategy == "heading_text":
        value = _first_text([
            page.get_by_role("heading", level=1),
            page.locator("h1"),
            page.locator("[data-testid='business-name']"),
        ])
        selector_hint = "role_h1" if value else "missing"
        return value, selector_hint

    if strategy == "label_next_value":
        labels = spec.get("labels") or [spec.get("label", "")]
        prefer_href = bool(spec.get("prefer_href", False))
        for idx, label in enumerate([label for label in labels if label], 1):
            value = _value_next_to_label(page, label, prefer_href=prefer_href)
            if value:
                return value, f"label_fallback_{idx}"
        return "", "missing"

    if strategy == "link_text_href":
        pattern = re.compile(spec.get("link_text", "website"), re.I)
        link = page.get_by_role("link", name=pattern).first
        if link.count() > 0:
            href = link.get_attribute("href") or ""
            return href.strip(), "link_href"
        return "", "missing"

    if strategy == "tel_link":
        link = page.locator("a[href^='tel:']").first
        if link.count() > 0:
            value = " ".join(link.inner_text().split())
            return value, "tel_link"
        return "", "missing"

    return "", selector_hint


def parse_bbb_profile(page: Page, url: str, profile_path: Path | None = None) -> dict[str, Any]:
    profile = _load_profile(profile_path)
    field_specs: list[dict[str, Any]] = profile.get("fields", [])
    extracted: dict[str, str] = {}
    selector_log: dict[str, str] = {}

    for spec in field_specs:
        field_name = spec.get("field_name", "").strip()
        if not field_name or extracted.get(field_name):
            continue
        value, hint = _extract_from_spec(page, spec)
        if value:
            extracted[field_name] = value
        selector_log[field_name] = hint

    extras: dict[str, str] = {}
    for field_name, value in extracted.items():
        target = "record" if field_name in KNOWN_RECORD_FIELDS else "extras"
        if target == "extras":
            extras[field_name] = value

    phone_primary = extracted.get("phone_primary", "")
    phones_all = extracted.get("phones_all", "") or phone_primary

    return {
        "business_name": extracted.get("business_name", ""),
        "website": extracted.get("website", ""),
        "phone_primary": phone_primary,
        "phones_all": phones_all,
        "years_in_business": extracted.get("years_in_business", ""),
        "customer_contact": extracted.get("customer_contact", ""),
        "address_full": extracted.get("address_full", ""),
        "source_url": url,
        "selector_log": selector_log,
        "extra_fields": extras,
    }
