from __future__ import annotations

import argparse
from pathlib import Path

from buyer_scout.commands.auth_bbb import run_auth_bbb
from buyer_scout.commands.crawl_bbb import run_crawl_bbb
from buyer_scout.commands.debug_bbb import run_debug_bbb
from buyer_scout.commands.discover_serp import run_discover_serp
from buyer_scout.commands.export import run_export
from buyer_scout.config import get_config, load_shared_env
from buyer_scout.core_store import CoreStore
from buyer_scout.parsers.bbb_profile_parser import DEFAULT_PROFILE_PATH
from buyer_scout.providers.bbb_browser import BBBBrowser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buyer-scout", description="Buyer lead acquisition CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth-bbb", help="Open BBB in headed mode and save auth state")
    auth.add_argument("--timeout-sec", type=int, default=600)

    crawl = sub.add_parser("crawl-bbb", help="Crawl BBB listings and profiles")
    crawl.add_argument("--query", required=True)
    crawl.add_argument("--location", required=True)
    crawl.add_argument("--max", type=int, default=25)
    crawl.add_argument("--max-profiles", type=int)
    crawl.add_argument("--headed", action="store_true")
    crawl.add_argument("--slowmo-ms", type=int, default=0)
    crawl.add_argument("--debug", action="store_true")
    crawl.add_argument("--trace", action="store_true")
    crawl.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    crawl.add_argument("--timeout-sec", type=int, default=60)

    serp = sub.add_parser("discover-serp", help="Discover leads from Google via SerpAPI")
    serp.add_argument("--query", required=True)
    serp.add_argument("--max", type=int, default=25)

    export = sub.add_parser("export", help="Export canonical buyer CSV")
    export.add_argument("--out", type=Path, default=Path("./data/buyers.csv"))

    debug = sub.add_parser("debug-bbb", help="Debug BBB selectors for one URL")
    debug.add_argument("--url", required=True)
    debug.add_argument("--headed", action="store_true", default=True)
    debug.add_argument("--slowmo-ms", type=int, default=0)
    debug.add_argument("--trace", action="store_true")
    debug.add_argument("--timeout-sec", type=int, default=60)

    return parser


def main() -> None:
    # Load shared dotenv early, before config/env reads.
    load_shared_env()

    parser = build_parser()
    args = parser.parse_args()
    cfg = get_config()
    store = CoreStore(cfg.db_path)
    out_csv = Path("./data/buyers.csv")

    if args.command == "auth-bbb":
        browser = BBBBrowser(auth_path=cfg.auth_path, headed=True, debug_dir=cfg.debug_dir)
        run_auth_bbb(browser, timeout_sec=args.timeout_sec)
        return

    if args.command == "crawl-bbb":
        max_results = args.max_profiles if args.max_profiles is not None else args.max
        browser = BBBBrowser(
            auth_path=cfg.auth_path,
            headed=args.headed,
            slowmo_ms=args.slowmo_ms,
            debug_dir=cfg.debug_dir,
            trace=args.trace,
        )
        run_crawl_bbb(
            store=store,
            browser=browser,
            query=args.query,
            location=args.location,
            max_results=max_results,
            out_csv=out_csv,
            debug=args.debug,
            profile_path=args.profile,
            timeout_sec=args.timeout_sec,
        )
        return

    if args.command == "discover-serp":
        run_discover_serp(store=store, query=args.query, max_results=args.max, out_csv=out_csv)
        return

    if args.command == "export":
        run_export(store=store, out=args.out)
        return

    if args.command == "debug-bbb":
        browser = BBBBrowser(
            auth_path=cfg.auth_path,
            headed=args.headed,
            slowmo_ms=args.slowmo_ms,
            debug_dir=cfg.debug_dir,
            trace=args.trace,
        )
        run_debug_bbb(browser=browser, url=args.url, timeout_sec=args.timeout_sec)
        return


if __name__ == "__main__":
    main()
