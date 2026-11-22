#!/usr/bin/env python3
"""
Investment OS Data Bridge - chiusure giornaliere per lista d'attesa e coda.

Fonte gratuita: API pubblica Nasdaq (storico giornaliero con data).
Scrive:
- data/current/watchlist_prices.csv  (ultima chiusura per ticker, con data)
- data/current/watchlist_history.csv (ultime ~10 sedute per ticker)
Nessun dato mancante viene trasformato in zero: se un ticker fallisce
la riga riporta status=MISSING.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "current"
TICKERS_FILE = ROOT / "data" / "watchlist_tickers.txt"

URL = "https://api.nasdaq.com/api/quote/{sym}/historical"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/",
}


def num(text):
    if text is None:
        return None
    t = str(text).replace("$", "").replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def fetch(sym: str, days: int = 20):
    today = dt.date.today()
    params = {
        "assetclass": "stocks",
        "fromdate": (today - dt.timedelta(days=days)).isoformat(),
        "todate": today.isoformat(),
        "limit": "50",
    }
    last_err = ""
    for attempt in range(3):
        try:
            r = requests.get(URL.format(sym=sym.replace(".", "/")), headers=HEADERS,
                             params=params, timeout=30)
            if r.status_code == 200:
                rows = (((r.json() or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
                out = []
                for row in rows:
                    d = dt.datetime.strptime(row["date"], "%m/%d/%Y").date().isoformat()
                    out.append({"date": d, "close": num(row.get("close")),
                                "volume": num(row.get("volume"))})
                out = [x for x in out if x["close"] is not None]
                out.sort(key=lambda x: x["date"])
                if out:
                    return out, ""
                last_err = "zero righe"
            else:
                last_err = f"HTTP {r.status_code}"
        except Exception as exc:  # rete o JSON
            last_err = type(exc).__name__
        time.sleep(2 + attempt * 3)
    return [], last_err


def main() -> int:
    tickers = [t.strip().upper() for t in TICKERS_FILE.read_text().splitlines()
               if t.strip() and not t.startswith("#")]
    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    latest, history, missing = [], [], 0
    for sym in tickers:
        rows, err = fetch(sym)
        if rows:
            last = rows[-1]
            prev = rows[-2]["close"] if len(rows) > 1 else None
            chg = round((last["close"] / prev - 1) * 100, 2) if prev else ""
            latest.append({"ticker": sym, "date": last["date"], "close": last["close"],
                           "prev_close": prev if prev is not None else "",
                           "change_pct": chg, "status": "PRESENT",
                           "source": "api.nasdaq.com historical", "fetched_at_utc": fetched_at})
            for x in rows[-10:]:
                history.append({"ticker": sym, "date": x["date"], "close": x["close"]})
        else:
            missing += 1
            latest.append({"ticker": sym, "date": "", "close": "", "prev_close": "",
                           "change_pct": "", "status": f"MISSING ({err})",
                           "source": "api.nasdaq.com historical", "fetched_at_utc": fetched_at})
        print(f"{sym}: {latest[-1]['status']} {latest[-1]['date']} {latest[-1]['close']}")
        time.sleep(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "watchlist_prices.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(latest[0].keys()))
        w.writeheader()
        w.writerows(latest)
    with open(OUT_DIR / "watchlist_history.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "date", "close"])
        w.writeheader()
        w.writerows(history)
    print(f"ticker: {len(tickers)}, missing: {missing}")
    return 1 if missing == len(tickers) else 0


if __name__ == "__main__":
    sys.exit(main())
