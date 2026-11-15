#!/usr/bin/env python3
"""Point-in-time market fields for R12 historical cases (research only).

Decision B1 (approved 2026-11-12, R12 historical validation ONLY): market cap =
unadjusted close on the last trading day <= as-of  x  dei:EntityCommonStockSharesOutstanding
reported on the cover of the latest 10-K filed <= as-of (all share classes summed).
The latest 10-Q cover filed <= as-of is used only as a consistency check: a difference above
20% (e.g. a split between the two dates) marks the row CONFLICTING. Never used for live decisions.
Writes the 8 BR-05 market columns in the canonical order.
"""
from __future__ import annotations

import json, os, sys, time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

import bridge

MARKET_COLS = ["market_price", "market_cap", "market_data_as_of", "market_data_retrieved_at_utc", "market_data_source",
               "market_data_source_symbol", "market_data_as_of_status", "market_data_status"]
SOURCE = "PIT_B1: FMP historical EOD non-split-adjusted close x SEC dei:EntityCommonStockSharesOutstanding (latest 10-K filed <= as_of)"


def cover_shares(d: bridge.Downloader, cik: str, as_of: int):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/EntityCommonStockSharesOutstanding.json"
    try:
        r = d.get_sec(url, timeout=60)
    except Exception as e:
        return None, None, f"companyconcept_error:{type(e).__name__}"
    facts = (r.json().get("units") or {}).get("shares") or []
    by = defaultdict(list)
    for f in facts:
        filed = int(str(f.get("filed", "0")).replace("-", "") or 0)
        if filed and filed <= as_of and f.get("form") in ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "40-F"):
            by[(f["form"].split("/")[0], f["accn"], filed)].append(f)

    def pick(forms):
        keys = [k for k in by if k[0] in forms]
        if not keys:
            return None
        k = max(keys, key=lambda z: z[2])
        latest_end = max(f["end"] for f in by[k])
        vals = [f["val"] for f in by[k] if f["end"] == latest_end]
        # several facts on the same date are separate share classes; exact duplicates are the same fact
        return dict(shares=float(sum(set(vals))),
                    accn=k[1], filed=k[2], end=latest_end)
    return pick(("10-K", "20-F", "40-F")), pick(("10-Q",)), ""


def price_at(symbol: str, as_of: int, key: str):
    """Unadjusted close on the last session <= as_of. Reads the committed price cache first;
    calls FMP only for symbols not cached, and stops calling it after repeated rate limits."""
    cache = _cache(as_of)
    if symbol in cache:
        c = cache[symbol]
        return float(c[0]), c[1], ""
    if _STATE["off"]:
        return None, None, "fmp_rate_limited_breaker"
    end = datetime.strptime(str(as_of), "%Y%m%d")
    url = "https://financialmodelingprep.com/stable/historical-price-eod/non-split-adjusted"
    params = dict(symbol=symbol, apikey=key, **{"from": (end - timedelta(days=12)).strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d")})
    err = "fmp_rate_limited"
    for attempt in range(3):
        try:
            time.sleep(0.25)
            r = requests.get(url, params=params, timeout=45)
            if r.status_code == 429:
                time.sleep(4 + attempt * 8)
                continue
            r.raise_for_status()
            data = r.json()
            rows = [x for x in (data if isinstance(data, list) else []) if int(x["date"].replace("-", "")) <= as_of]
            _STATE["limited"] = 0
            if not rows:
                return None, None, "no_price_rows"
            x = max(rows, key=lambda z: z["date"])
            close = x.get("adjClose") if x.get("close") is None else x.get("close")
            cache[symbol] = [float(close), x["date"]]
            return float(close), x["date"], ""
        except Exception as e:
            err = f"fmp_error:{type(e).__name__}"
            time.sleep(1.5)
    if err == "fmp_rate_limited":
        _STATE["limited"] += 1
        if _STATE["limited"] >= 3:
            _STATE["off"] = True
            print("PIT_MARKET_BREAKER=FMP rate limit persists; remaining symbols left MISSING for this run", flush=True)
    return None, None, err


_STATE = {"limited": 0, "off": False}
_CACHES: dict = {}
CACHE_DIR = Path(__file__).resolve().parents[1] / "pit" / "cache"


def _cache(as_of: int) -> dict:
    if as_of not in _CACHES:
        f = Path(os.environ.get("PIT_PRICE_CACHE_DIR", CACHE_DIR)) / f"prices_{as_of}.json"
        _CACHES[as_of] = json.loads(f.read_text()) if f.exists() else {}
    return _CACHES[as_of]


def save_cache(as_of: int) -> Path:
    d = Path(os.environ.get("PIT_PRICE_CACHE_DIR", CACHE_DIR)); d.mkdir(parents=True, exist_ok=True)
    f = d / f"prices_{as_of}.json"
    f.write_text(json.dumps(_cache(as_of), indent=0, sort_keys=True))
    return f


def main() -> int:
    as_of = int(os.environ["PIT_AS_OF"])
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise SystemExit("PIT_MARKET_BLOCK: FMP_API_KEY missing")
    path = Path(__file__).resolve().parents[1] / "data" / "current" / "sp500_fundamentals.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if any(c in df.columns for c in MARKET_COLS):
        raise SystemExit("PIT_MARKET_BLOCK: market columns already present")
    d = bridge.Downloader()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    out = {c: [] for c in MARKET_COLS}
    stats = defaultdict(int)
    for _, row in df.iterrows():
        sym = row.get("ticker_sec") or row["ticker"]
        cik = str(row.get("cik") or "").zfill(10) if row.get("cik") else ""
        price, pdate, perr = price_at(sym, as_of, key)
        time.sleep(0.25)
        k10, q10, serr = cover_shares(d, cik, as_of) if cik else (None, None, "no_cik")
        status, mcap = "MISSING", ""
        if price is not None and k10 and k10["shares"] > 0:
            mcap_v = price * k10["shares"]
            mcap = repr(mcap_v)
            status = "PRESENT"
            if q10 and q10["shares"] > 0 and q10["filed"] > k10["filed"] and abs(q10["shares"] / k10["shares"] - 1) > 0.20:
                status = "CONFLICTING"
        stats[status] += 1
        stats["no_price"] += price is None
        stats["no_shares"] += not k10
        out["market_price"].append("" if price is None else repr(price))
        out["market_cap"].append(mcap)
        out["market_data_as_of"].append(pdate or "")
        out["market_data_retrieved_at_utc"].append(now)
        out["market_data_source"].append(SOURCE + (f" | shares_accn={k10['accn']} filed={k10['filed']}" if k10 else "") + (f" | {perr}" if perr else "") + (f" | {serr}" if serr else ""))
        out["market_data_source_symbol"].append(sym)
        out["market_data_as_of_status"].append("PRESENT" if pdate else "MISSING")
        out["market_data_status"].append(status)
    for c in MARKET_COLS:
        df[c] = out[c]
    df.to_csv(path, index=False)
    print("PIT_MARKET=" + json.dumps(dict(as_of=as_of, rows=len(df), **stats)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
