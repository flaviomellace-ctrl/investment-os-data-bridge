#!/usr/bin/env python3
"""
Investment OS Data Bridge — probe Nasdaq public screener market data.

Read-only probe:
- fetches Nasdaq's public stock screener dataset;
- checks whether price and marketCap are available for the current S&P 500 universe;
- prints only aggregate coverage, never rankings or recommendations;
- writes no repository files.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = ROOT / "data" / "current" / "sp500_universe.csv"

NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/",
}


def clean_symbol(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper().replace("/", ".")


def symbol_variants(symbol: str) -> list[str]:
    variants = [symbol]
    if "." in symbol:
        variants.append(symbol.replace(".", "-"))
    if "-" in symbol:
        variants.append(symbol.replace("-", "."))
    return list(dict.fromkeys(variants))


def parse_price(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        x = float(text)
    except ValueError:
        return None
    return x if math.isfinite(x) and x > 0 else None


def parse_market_cap(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        x = float(text)
    except ValueError:
        return None
    return x if math.isfinite(x) and x > 0 else None


def main() -> int:
    if not UNIVERSE_PATH.exists():
        raise SystemExit("sp500_universe.csv non trovato")

    universe = pd.read_csv(UNIVERSE_PATH, low_memory=False)
    tickers = [clean_symbol(x) for x in universe["ticker"].tolist()]
    tickers = [x for x in tickers if x]

    response = requests.get(
        NASDAQ_URL,
        headers=HEADERS,
        params={
            "tableonly": "true",
            "limit": "10000",
            "offset": "0",
            "download": "true",
        },
        timeout=45,
    )

    print(f"nasdaq_screener: HTTP {response.status_code}")
    if response.status_code != 200:
        raise SystemExit("Nasdaq screener non raggiungibile")

    payload = response.json()
    rows = ((payload or {}).get("data") or {}).get("rows") or []

    print(f"nasdaq rows: {len(rows)}")
    if not rows:
        raise SystemExit("Nasdaq screener ha restituito zero righe")

    market = {}
    for row in rows:
        symbol = clean_symbol(row.get("symbol"))
        if not symbol:
            continue

        price = parse_price(
            row.get("lastsale")
            if row.get("lastsale") is not None
            else row.get("lastSalePrice")
        )
        cap = parse_market_cap(row.get("marketCap"))

        market[symbol] = {
            "price": price,
            "market_cap": cap,
        }

    found = 0
    complete = 0

    for ticker in tickers:
        record = None
        for candidate in symbol_variants(ticker):
            if candidate in market:
                record = market[candidate]
                break

        if record is not None:
            found += 1
            if record["price"] is not None and record["market_cap"] is not None:
                complete += 1

    total = len(tickers)
    found_pct = round(found / total * 100, 1) if total else 0.0
    complete_pct = round(complete / total * 100, 1) if total else 0.0

    print(f"S&P universe: {total}")
    print(f"ticker matched: {found}/{total} = {found_pct:.1f}%")
    print(
        f"price + direct marketCap complete: "
        f"{complete}/{total} = {complete_pct:.1f}%"
    )
    print("market cap ricostruita da bridge shares: NO")
    print("repository files written: NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
