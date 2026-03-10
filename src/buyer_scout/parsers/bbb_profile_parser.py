from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page


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


def _load_profile(profile_path: Path | None) -> dict[str, Any]:
    resolved = profile_path or DEFAULT_PROFILE_PATH
    return json.loads(resolved.read_text(encoding="utf-8"))


def _extract_labeled_value(page: Page, labels: list[str]) -> str:
    for label in labels:
        pattern_label = label.rstrip("?")
        dts = page.locator("dt")
        for i in range(dts.count()):
            dt = dts.nth(i)
            if re.search(pattern_label, dt.inner_text(), re.IGNORECASE):
                dd = dt.locator("xpath=following-sibling::dd[1]")
                if dd.count() > 0:
                    return " ".join(dd.first.inner_text().split())

    text = page.inner_text("body")
    for label in labels:
        pattern = re.compile(rf"{label}\s*[:\-]?\s*(.+)", re.IGNORECASE)
        for line in text.splitlines():
            match = pattern.match(line.strip())
            if match:
                return match.group(1).strip()
    return ""


def _name_from_url(url: str) -> str:
    parts = url.rstrip("/").split("/profile/")
    if len(parts) < 2:
        return ""
    slug = parts[1].split("/")[-1]
    slug = re.sub(r"-\d{4}-\d+$", "", slug)
    return slug.replace("-", " ").title()


def parse_bbb_profile(page: Page, url: str, profile_path: Path | None = None) -> dict[str, Any]:
    _load_profile(profile_path)

    business_name = ""
    selector_log: dict[str, str] = {}

    loc = page.locator("#businessName")
    if loc.count() > 0:
        business_name = " ".join(loc.first.inner_text().split())
        selector_log["business_name"] = "#businessName"

    if not business_name:
        title = page.title()
        if "|" in title:
            business_name = " ".join(title.split("|")[0].split()).strip()
            selector_log["business_name"] = "title"

    if not business_name:
        business_name = _name_from_url(page.url)
        selector_log["business_name"] = "url_slug"

    website = ""
    visit_link = page.locator("a:has-text('Visit Website')")
    if visit_link.count() > 0:
        website = visit_link.first.get_attribute("href") or ""
        selector_log["website"] = "visit_website_link"

    phone_primary = ""
    tel_link = page.locator("a[href^='tel:']")
    if tel_link.count() > 0:
        phone_primary = (tel_link.first.get_attribute("href") or "").replace("tel:", "")
        selector_log["phone_primary"] = "tel_link"

    principal_contact = _extract_labeled_value(page, ["Principal Contacts?", "Principal Contact"])
    business_started = _extract_labeled_value(page, ["Business Started", "Date Business Started"])

    if principal_contact:
        selector_log["principal_contact"] = "labeled_value"
    if business_started:
        selector_log["business_started"] = "labeled_value"

    extras: dict[str, str] = {}
    if principal_contact:
        extras["principal_contact"] = principal_contact
    if business_started:
        extras["business_started"] = business_started

    return {
        "business_name": business_name,
        "website": website,
        "phone_primary": phone_primary,
        "phones_all": phone_primary,
        "years_in_business": "",
        "customer_contact": principal_contact,
        "principal_contact": principal_contact,
        "business_started": business_started,
        "address_full": "",
        "source_url": url,
        "selector_log": selector_log,
        "extra_fields": extras,
    }
