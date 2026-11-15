#!/usr/bin/env python3
"""Fill the point-in-time price cache (unadjusted closes) for the configured as-of dates.

Light job, separate from the heavy replay: it can be re-run across provider quota windows and
each run adds to pit/cache/prices_<as_of>.json. Source: FMP historical-price-eod/non-split-adjusted,
last session <= as-of (decision B1). Nothing after the as-of date is requested.
"""
import json, os, sys, tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

import pit_market, pit_universe


def main() -> int:
    cfg = json.loads((Path(__file__).resolve().parents[1] / "pit" / "run_config.json").read_text())
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise SystemExit("PIT_PRICES_BLOCK: FMP_API_KEY missing")
    report = {}
    for a in cfg["as_of_list"]:
        as_of = int(a)
        with tempfile.TemporaryDirectory() as t:
            u = Path(t) / "universe.csv"
            pit_universe.main_revision(as_of, u)
            syms = pd.read_csv(u, dtype=str, keep_default_na=False)["ticker_sec"].tolist()
        got = miss = 0
        for s in syms:
            price, _, _ = pit_market.price_at(s, as_of, key)
            got += price is not None
            miss += price is None
        pit_market.save_cache(as_of)
        report[str(as_of)] = dict(symbols=len(syms), cached=got, missing=miss)
        pit_market._STATE.update(limited=0, off=pit_market._STATE["off"])
    out = Path(__file__).resolve().parents[1] / "pit" / "cache" / "prices_report.json"
    out.write_text(json.dumps(dict(retrieved_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                                   source="FMP stable/historical-price-eod/non-split-adjusted", unit="price per share, listing currency",
                                   breaker_tripped=pit_market._STATE["off"], dates=report), indent=1))
    print("PIT_PRICES=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
