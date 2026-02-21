from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import requests


class SerpAPIProvider:
    SEARCH_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("SERPAPI_API_KEY is required for discover-serp")

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    @staticmethod
    def _phones(text: str) -> str:
        matches = re.findall(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text or "")
        return "|".join(dict.fromkeys(matches))

    @staticmethod
    def _emails(text: str) -> str:
        matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text or "")
        return "|".join(dict.fromkeys(matches))

    def search(self, query: str, max_results: int) -> list[dict[str, str]]:
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": max_results,
        }
        response = requests.get(self.SEARCH_URL, params=params, timeout=45)
        response.raise_for_status()
        payload = response.json()

        out: list[dict[str, str]] = []
        for item in (payload.get("organic_results") or [])[:max_results]:
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            out.append(
                {
                    "business_name": item.get("title", ""),
                    "website": link,
                    "domain": self._domain(link),
                    "phone_primary": self._phones(snippet).split("|")[0] if self._phones(snippet) else "",
                    "phones_all": self._phones(snippet),
                    "contact_email": self._emails(snippet).split("|")[0] if self._emails(snippet) else "",
                    "emails_all": self._emails(snippet),
                    "source_url": link,
                    "position": str(item.get("position", "")),
                    "snippet": snippet,
                }
            )
        return out
