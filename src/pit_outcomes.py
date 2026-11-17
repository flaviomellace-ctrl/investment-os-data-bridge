#!/usr/bin/env python3
"""R12 historical outcomes: 24-month total return (dividend- and split-adjusted) for every universe member.

Runs only after the executor output is frozen (docs/r12/executor_20261117). Source order: Yahoo Finance chart
API (adjclose), then FMP dividend-adjusted EOD. Delisted names: last available price before the end date,
flagged. Missing names are reported, never set to zero.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PAIRS = {20231114: 20251114, 20241114: 20261113}


def ts(d):
    return int(datetime.strptime(str(d), "%Y%m%d").replace(tzinfo=timezone.utc).timestamp())


def yahoo(sym, a, b):
    for host in ("query1", "query2"):
        try:
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}",
                             params=dict(period1=ts(a) - 12 * 86400, period2=ts(b) + 2 * 86400, interval="1d", events="div,split"),
                             headers=H, timeout=10)
            if r.status_code == 429:
                time.sleep(5); continue
            if r.status_code != 200:
                continue
            R = r.json()["chart"]["result"][0]
            t = R["timestamp"]; c = R["indicators"]["adjclose"][0]["adjclose"]
            return [(datetime.fromtimestamp(x, timezone.utc).strftime("%Y%m%d"), v) for x, v in zip(t, c) if v is not None], "yahoo"
        except Exception:
            continue
    return None, "yahoo_fail"


def fmp(sym, a, b, key):
    if not key:
        return None, "no_fmp_key"
    try:
        r = requests.get("https://financialmodelingprep.com/stable/historical-price-eod/dividend-adjusted",
                         params={"symbol": sym, "apikey": key, "from": str(a)[:4] + "-" + str(a)[4:6] + "-" + str(int(str(a)[6:]) - 10 if int(str(a)[6:]) > 10 else 1).zfill(2),
                                 "to": f"{str(b)[:4]}-{str(b)[4:6]}-{str(b)[6:]}"}, timeout=45)
        if r.status_code != 200:
            return None, f"fmp_{r.status_code}"
        rows = [(x["date"].replace("-", ""), x.get("adjClose")) for x in r.json() if x.get("adjClose") is not None]
        return sorted(rows), "fmp"
    except Exception as e:
        return None, f"fmp_{type(e).__name__}"


def main():
    key = os.environ.get("FMP_API_KEY", "")
    out = {}
    probe_y, _ = yahoo("AAPL", 20241114, 20241120)
    probe_f, fsrc = fmp("AAPL", 20241114, 20241120, key)
    use_y, use_f = bool(probe_y), bool(probe_f)
    print("PIT_OUTCOMES_PROBE=" + json.dumps(dict(yahoo=use_y, fmp=use_f, fmp_status=fsrc)), flush=True)
    if not (use_y or use_f):
        raise SystemExit("PIT_OUTCOMES_BLOCK: neither Yahoo nor FMP reachable from CI")
    for a, b in PAIRS.items():
        u = pd.read_csv(ROOT / "pit" / "out" / "r12-historical-v1" / str(a) / "universe.csv", dtype=str, keep_default_na=False)
        res = {}
        for sym in u["ticker_sec"]:
            series, src = yahoo(sym, a, b) if use_y else (None, "yahoo_skipped")
            if not series and use_f:
                series, src = fmp(sym, a, b, key)
            time.sleep(0.3)
            if not series:
                res[sym] = dict(status="MISSING", source=src); continue
            p0 = [x for x in series if x[0] <= str(a)]
            p1 = [x for x in series if x[0] <= str(b)]
            if not p0:
                res[sym] = dict(status="MISSING", source=src, reason="no price at as-of"); continue
            d0, v0 = p0[-1]; d1, v1 = p1[-1]
            st = "PRESENT" if d1 >= str(b - 7) else "DELISTED_LAST_PRICE"
            res[sym] = dict(status=st, source=src, d0=d0, p0=v0, d1=d1, p1=v1, ret=round((v1 / v0 - 1) * 100, 2))
        out[str(a)] = dict(end=b, members=len(u), results=res,
                           counts={k: sum(1 for v in res.values() if v["status"] == k) for k in ("PRESENT", "DELISTED_LAST_PRICE", "MISSING")})
        print("PIT_OUTCOMES=" + json.dumps({"as_of": a, **out[str(a)]["counts"]}), flush=True)
    p = ROOT / "pit" / "out" / "outcomes_24m.json"
    p.write_text(json.dumps(dict(schema="r12_outcomes_v1", retrieved_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                                 measure="total return, adjusted close, as-of to last session <= end date", dates=out), indent=0))


if __name__ == "__main__":
    sys.exit(main())
