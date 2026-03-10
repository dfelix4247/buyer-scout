from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

from playwright.sync_api import BrowserContext, Locator, Page, sync_playwright


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
        base_url: str = "https://www.bbb.org/",
    ):
        self.auth_path = auth_path
        self.headed = headed
        self.slowmo_ms = slowmo_ms
        self.debug_dir = debug_dir
        self.trace = trace
        self.base_url = base_url

    def _new_context(self, with_storage_state: bool = True) -> tuple[Any, Any, BrowserContext, BrowserDebugArtifacts]:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=not self.headed, slow_mo=self.slowmo_ms)
        kwargs: dict[str, str] = {}
        if with_storage_state and self.auth_path.exists():
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

    def _write_debug_snapshot(self, page: Page, out_dir: Path, stem: str = "page") -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{stem}.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(out_dir / f"{stem}.png"), full_page=True)

    @staticmethod
    def _has_signin_ui(page: Page) -> bool:
        return page.locator("a:has-text('Sign in'), button:has-text('Sign in')").count() > 0

    @staticmethod
    def _has_account_ui(page: Page) -> bool:
        selectors = [
            "a:has-text('My BBB')",
            "button:has-text('My BBB')",
            "a:has-text('Account')",
            "button:has-text('Account')",
            "[aria-label*='account' i]",
            "[data-testid*='account' i]",
        ]
        return any(page.locator(sel).count() > 0 for sel in selectors)

    def assert_logged_in(self, page: Page, artifact_stem: str = "not_authenticated") -> None:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except Exception:
            pass

        url = page.url.lower()
        html_lower = page.content().lower()
        if "/account/login" in url or "too many redirects" in html_lower:
            if self.debug_dir:
                self._write_debug_snapshot(page, self.debug_dir, artifact_stem)
            raise RuntimeError("Not authenticated; run `buyer-scout auth-bbb` first.")

        if self._has_signin_ui(page) and not self._has_account_ui(page):
            if self.debug_dir:
                self._write_debug_snapshot(page, self.debug_dir, artifact_stem)
            raise RuntimeError("Not authenticated; run `buyer-scout auth-bbb` first.")

    def _launch_persistent_auth_context(self, user_data_dir: Path) -> tuple[Any, BrowserContext]:
        pw = sync_playwright().start()
        launch_kwargs = {
            "user_data_dir": str(user_data_dir),
            "headless": False,
            "slow_mo": self.slowmo_ms,
            "args": ["--start-maximized", "--disable-blink-features=AutomationControlled"],
            "no_viewport": True,
        }

        for channel in ("chrome", "msedge", None):
            try:
                if channel:
                    context = pw.chromium.launch_persistent_context(channel=channel, **launch_kwargs)
                else:
                    context = pw.chromium.launch_persistent_context(**launch_kwargs)
                return pw, context
            except Exception:
                continue

        pw.stop()
        raise RuntimeError("Unable to start persistent browser context for BBB auth")

    def auth_login(self, timeout_sec: int = 600) -> None:
        user_data_dir = self.auth_path.parent / "chrome_profile_auth_tmp"
        if user_data_dir.exists():
            shutil.rmtree(user_data_dir, ignore_errors=True)
        user_data_dir.mkdir(parents=True, exist_ok=True)

        pw, context = self._launch_persistent_auth_context(user_data_dir)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(urljoin(self.base_url, "/account/login"), wait_until="domcontentloaded", timeout=60_000)
            if self.debug_dir:
                self._write_debug_snapshot(page, self.debug_dir, "auth_prelogin")

            print("=" * 60)
            print("Log in with your BBB account in the browser window.")
            print("If Google sign-in hangs, close the auth window and rerun auth-bbb.")
            print("When you are fully logged in, come back here and press Enter.")
            print("=" * 60)
            input("  >>> Press Enter after logging in: ")

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10_000)
                except Exception:
                    pass

            page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            self.assert_logged_in(page, artifact_stem="auth_postlogin")

            self.auth_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(self.auth_path))
            print(f"Saved auth state to {self.auth_path}")
        except Exception:
            if self.debug_dir and 'page' in locals():
                self._write_debug_snapshot(page, self.debug_dir, "auth_failed")
            raise RuntimeError("auth failed; delete auth.json and retry")
        finally:
            context.close()
            pw.stop()
            shutil.rmtree(user_data_dir, ignore_errors=True)

    def require_auth(self) -> None:
        if not self.auth_path.exists():
            raise RuntimeError("Auth state missing; run `buyer-scout auth-bbb` first.")

    @staticmethod
    def _first_visible_enabled(candidates: Locator) -> Locator | None:
        for i in range(candidates.count()):
            candidate = candidates.nth(i)
            if candidate.is_visible() and candidate.is_enabled():
                return candidate
        return None

    @staticmethod
    def _fill_with_fallback(input_locator: Locator, value: str) -> None:
        input_locator.click()
        try:
            input_locator.fill(value)
        except Exception:
            input_locator.type(value, delay=20)

    def _fill_search_inputs(self, page: Page, query: str, location: str) -> None:
        find_candidates = page.locator(
            "input[placeholder*='find' i], input[aria-label*='find' i], input[name*='find' i]"
        )
        near_candidates = page.locator(
            "input[placeholder*='near' i], input[aria-label*='near' i], input[name*='loc' i]"
        )

        find_input = self._first_visible_enabled(find_candidates)
        near_input = self._first_visible_enabled(near_candidates)

        if not find_input or not near_input:
            if self.debug_dir:
                self._write_debug_snapshot(page, self.debug_dir, "crawl_inputs_not_found")
            raise RuntimeError("BBB search inputs not found/visible.")

        self._fill_with_fallback(find_input, query)
        self._fill_with_fallback(near_input, location)
        near_input.press("Enter")

    def _navigate_search_results(self, page: Page, query: str, location: str, timeout_sec: int) -> None:
        params = urlencode({"find_text": query, "find_loc": location})
        search_url = f"{self.base_url.rstrip('/')}/search?{params}"
        print(f"Navigating to search URL: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

    def _wait_for_results(self, page: Page, timeout_sec: int) -> None:
        end = time.time() + timeout_sec
        while time.time() < end:
            if page.locator("a[href*='/profile/']").count() > 0:
                return
            body = ""
            try:
                body = page.inner_text("body")
            except Exception:
                pass
            lower = body.lower()
            if "results for" in lower or "category:" in lower:
                return
            if "no results" in lower or "0 results" in lower:
                if self.debug_dir:
                    self._write_debug_snapshot(page, self.debug_dir, "crawl_no_results")
                raise RuntimeError("BBB returned no results for this search.")
            time.sleep(1)
        if self.debug_dir:
            self._write_debug_snapshot(page, self.debug_dir, "crawl_results_timeout")
        raise TimeoutError("Search results did not appear in time.")

    def _collect_page_urls(self, page: Page, seen: set[str], max_count: int) -> list[str]:
        urls: list[str] = []
        links = page.locator("a[href*='/profile/']")
        for i in range(links.count()):
            if len(seen) + len(urls) >= max_count:
                break
            href = links.nth(i).get_attribute("href")
            if not href:
                continue
            full_url = urljoin(page.url, href)
            if full_url not in seen:
                urls.append(full_url)
        return urls

    def _click_next_page(self, page: Page) -> bool:
        for sel in (
            "button[aria-label*='next' i]",
            "a[aria-label*='next' i]",
            "[class*='pagination'] button:has-text('Next')",
            "[class*='pagination'] a:has-text('Next')",
            "button:has-text('Next')",
            "a:has-text('Next')",
        ):
            loc = page.locator(sel)
            if loc.count() == 0:
                continue
            el = self._first_visible_enabled(loc)
            if not el:
                continue
            disabled = el.get_attribute("disabled")
            aria_disabled = el.get_attribute("aria-disabled")
            if disabled is not None or aria_disabled == "true":
                return False
            try:
                el.click()
                page.wait_for_load_state("domcontentloaded", timeout=15_000)
                self._wait_for_results(page, timeout_sec=30)
                return True
            except Exception:
                continue
        return False

    def collect_results(self, query: str, location: str, max_results: int, timeout_sec: int = 60) -> list[dict[str, str]]:
        self.require_auth()
        pw, browser, context, _ = self._new_context(with_storage_state=True)
        try:
            page = context.new_page()
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            self.assert_logged_in(page)
            self._navigate_search_results(page, query, location, timeout_sec=timeout_sec)
            self._wait_for_results(page, timeout_sec=timeout_sec)

            urls: list[str] = []
            seen: set[str] = set()
            while len(urls) < max_results:
                page_urls = self._collect_page_urls(page, seen, max_results)
                for u in page_urls:
                    seen.add(u)
                    urls.append(u)
                    if len(urls) >= max_results:
                        break
                if len(urls) >= max_results or not self._click_next_page(page):
                    break
            if not urls:
                if self.debug_dir:
                    self._write_debug_snapshot(page, self.debug_dir, "crawl_no_profile_urls")
                raise RuntimeError("No BBB profile URLs found on results pages.")
            return [{"url": u, "name": ""} for u in urls]
        finally:
            context.close()
            browser.close()
            pw.stop()

    def debug_url(self, url: str, out_dir: Path, timeout_sec: int = 60) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        self.require_auth()
        pw, browser, context, artifacts = self._new_context(with_storage_state=True)
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            self.assert_logged_in(page, artifact_stem="debug_not_authenticated")
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

    def scrape_profile(self, url: str, artifact_dir: Path | None = None, timeout_sec: int = 60) -> dict[str, Any]:
        self.require_auth()
        pw, browser, context, artifacts = self._new_context(with_storage_state=True)
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            if artifact_dir:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / "page.html").write_text(page.content(), encoding="utf-8")
                page.screenshot(path=str(artifact_dir / "screenshot.png"), full_page=True)
            if self.trace and self.debug_dir:
                context.tracing.stop(path=str(self.debug_dir / f"trace-{int(time.time())}.zip"))
            return {
                "page": page,
                "html": page.content(),
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
