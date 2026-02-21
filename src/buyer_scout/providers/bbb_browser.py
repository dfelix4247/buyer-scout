from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, sync_playwright


@dataclass(slots=True)
class BrowserDebugArtifacts:
    console_messages: list[str]
    network_events: list[dict[str, Any]]


class BBBBrowser:
    def __init__(
        self,
        auth_path: Path,
        headed: bool = False,
        slowmo_ms: int = 0,
        debug_dir: Path | None = None,
        trace: bool = False,
    ):
        self.auth_path = auth_path
        self.headed = headed
        self.slowmo_ms = slowmo_ms
        self.debug_dir = debug_dir
        self.trace = trace

    def _new_context(self) -> tuple[Any, Any, BrowserContext, BrowserDebugArtifacts]:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=not self.headed, slow_mo=self.slowmo_ms)
        kwargs = {}
        if self.auth_path.exists():
            kwargs["storage_state"] = str(self.auth_path)
        context = browser.new_context(**kwargs)
        artifacts = BrowserDebugArtifacts(console_messages=[], network_events=[])

        def on_console(msg: Any) -> None:
            artifacts.console_messages.append(f"[{msg.type}] {msg.text}")

        def on_response(resp: Any) -> None:
            req = resp.request
            artifacts.network_events.append(
                {
                    "url": resp.url,
                    "status": resp.status,
                    "type": req.resource_type,
                    "method": req.method,
                }
            )

        context.on("console", on_console)
        context.on("response", on_response)
        if self.trace and self.debug_dir:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        return pw, browser, context, artifacts

    def auth_login(self) -> None:
        pw, browser, context, _ = self._new_context()
        try:
            page = context.new_page()
            page.goto("https://www.bbb.org/", wait_until="domcontentloaded")
            print("Please complete login in the opened browser, then press Enter here...")
            input()
            self.auth_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(self.auth_path))
            print(f"Saved auth state to {self.auth_path}")
        finally:
            context.close()
            browser.close()
            pw.stop()

    def require_auth(self) -> None:
        if not self.auth_path.exists():
            raise RuntimeError("Run buyer-scout auth-bbb again.")

    def collect_results(self, query: str, location: str, max_results: int) -> list[dict[str, str]]:
        self.require_auth()
        pw, browser, context, _ = self._new_context()
        results: list[dict[str, str]] = []
        try:
            page = context.new_page()
            page.goto("https://www.bbb.org/", wait_until="domcontentloaded")
            page.get_by_role("textbox", name="Search").fill(query)
            page.get_by_role("textbox", name="Near").fill(location)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            cards = page.locator("a[href*='/us/']")
            seen: set[str] = set()
            for idx in range(min(cards.count(), max_results * 3)):
                href = cards.nth(idx).get_attribute("href") or ""
                name = cards.nth(idx).inner_text().strip()
                if not href or "/profile/" not in href:
                    continue
                url = href if href.startswith("http") else f"https://www.bbb.org{href}"
                if url in seen:
                    continue
                seen.add(url)
                results.append({"url": url, "name": name})
                if len(results) >= max_results:
                    break
            return results
        finally:
            context.close()
            browser.close()
            pw.stop()

    def debug_url(self, url: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        pw, browser, context, artifacts = self._new_context()
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            (out_dir / "page.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(out_dir / "screenshot.png"), full_page=True)
            (out_dir / "console.log").write_text("\n".join(artifacts.console_messages), encoding="utf-8")
            (out_dir / "network.json").write_text(json.dumps(artifacts.network_events, indent=2), encoding="utf-8")
            meta = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "viewport": page.viewport_size,
                "user_agent": page.evaluate("() => navigator.userAgent"),
                "auth_state_used": self.auth_path.exists(),
            }
            (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            if self.trace and self.debug_dir:
                context.tracing.stop(path=str(self.debug_dir / "trace.zip"))
        finally:
            context.close()
            browser.close()
            pw.stop()

    def scrape_profile(self, url: str, pause_ms: int = 500, artifact_dir: Path | None = None) -> dict[str, Any]:
        self.require_auth()
        pw, browser, context, artifacts = self._new_context()
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(pause_ms)
            html = page.content()
            if artifact_dir:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / "page.html").write_text(html, encoding="utf-8")
                page.screenshot(path=str(artifact_dir / "screenshot.png"), full_page=True)
            if self.trace and self.debug_dir:
                context.tracing.stop(path=str(self.debug_dir / f"trace-{int(time.time())}.zip"))
            return {
                "page": page,
                "html": html,
                "console": artifacts.console_messages,
                "network": artifacts.network_events,
                "context": context,
                "browser": browser,
                "pw": pw,
            }
        except Exception:
            context.close()
            browser.close()
            pw.stop()
            raise

    @staticmethod
    def close_scrape_session(session: dict[str, Any]) -> None:
        session["context"].close()
        session["browser"].close()
        session["pw"].stop()
