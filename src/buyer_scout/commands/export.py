from __future__ import annotations

from pathlib import Path

from buyer_scout.core_store import CoreStore


def run_export(store: CoreStore, out: Path) -> None:
    store.export_buyers_csv(out)
    print(f"Exported buyers CSV to {out}")
