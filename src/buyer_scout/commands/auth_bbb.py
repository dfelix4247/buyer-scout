from __future__ import annotations

from buyer_scout.providers.bbb_browser import BBBBrowser


def run_auth_bbb(browser: BBBBrowser, timeout_sec: int) -> None:
    browser.auth_login(timeout_sec=timeout_sec)
