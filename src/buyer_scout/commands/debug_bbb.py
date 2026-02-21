from __future__ import annotations

from datetime import datetime

from buyer_scout.providers.bbb_browser import BBBBrowser


def run_debug_bbb(browser: BBBBrowser, url: str) -> None:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out_dir = browser.debug_dir / f"run-{stamp}" if browser.debug_dir else None
    if out_dir is None:
        raise RuntimeError("Debug directory is not configured")
    browser.debug_url(url=url, out_dir=out_dir)
    print(f"Wrote debug artifacts to {out_dir}")
