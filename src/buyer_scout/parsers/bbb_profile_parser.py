from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import Locator, Page


LABELS = {
    "website": ["Business Website", "Website"],
    "phone": ["Phone Number", "Phone"],
    "years_in_business": ["Years in Business", "Years in business"],
    "customer_contact": ["Business Management", "Customer Contact"],
    "address": ["Business Address", "Address"],
}


def _value_next_to_label(page: Page, label: str) -> str:
    label_loc = page.get_by_text(label, exact=False).first
    if label_loc.count() == 0:
        return ""
    candidate = label_loc.locator("xpath=following::*[self::a or self::p or self::span or self::div][1]")
    if candidate.count() == 0:
        return ""
    return candidate.first.inner_text().strip()


def _first_text(locators: list[Locator]) -> str:
    for locator in locators:
        if locator.count() > 0:
            txt = locator.first.inner_text().strip()
            if txt:
                return txt
    return ""


def parse_bbb_profile(page: Page, url: str) -> dict[str, Any]:
    selector_log: dict[str, str] = {}

    name = _first_text([
        page.get_by_role("heading", level=1),
        page.locator("h1"),
        page.locator("[data-testid='business-name']"),
    ])
    selector_log["name"] = "role_h1" if name else "missing"

    website = ""
    for idx, label in enumerate(LABELS["website"], 1):
        website = _value_next_to_label(page, label)
        if website:
            selector_log["website"] = f"label_fallback_{idx}"
            break
    if not website:
        website = _first_text([page.get_by_role("link", name=re.compile("website", re.I))])
        selector_log["website"] = "link_fallback" if website else "missing"

    phone = ""
    for idx, label in enumerate(LABELS["phone"], 1):
        phone = _value_next_to_label(page, label)
        if phone:
            selector_log["phone"] = f"label_fallback_{idx}"
            break
    if not phone:
        phone = _first_text([page.locator("a[href^='tel:']")])
        selector_log["phone"] = "tel_link" if phone else "missing"

    years = ""
    for idx, label in enumerate(LABELS["years_in_business"], 1):
        years = _value_next_to_label(page, label)
        if years:
            selector_log["years_in_business"] = f"label_fallback_{idx}"
            break

    contact = ""
    for idx, label in enumerate(LABELS["customer_contact"], 1):
        contact = _value_next_to_label(page, label)
        if contact:
            selector_log["customer_contact"] = f"label_fallback_{idx}"
            break

    address = ""
    for idx, label in enumerate(LABELS["address"], 1):
        address = _value_next_to_label(page, label)
        if address:
            selector_log["address"] = f"label_fallback_{idx}"
            break

    return {
        "business_name": name,
        "website": website,
        "phone_primary": phone,
        "phones_all": phone,
        "years_in_business": years,
        "customer_contact": contact,
        "address_full": address,
        "source_url": url,
        "selector_log": selector_log,
    }
