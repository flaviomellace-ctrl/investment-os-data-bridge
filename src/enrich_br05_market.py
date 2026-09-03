#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-05 market data enrichment.

Adds current market price and market capitalization from the FMP stable
single-symbol quote endpoint.

Integrity rules:
- FMP_API_KEY is read only from the environment.
- The API key is never printed or written to disk.
- Market cap is accepted only when returned directly by FMP.
- Market cap is NEVER reconstructed from bridge share counts.
- MISSING is never converted to zero.
- No BQS, IOS, ranking, deep dive, or recommendation is computed here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

import bridge


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "current"

FUNDAMENTALS_PATH = DATA_DIR / "sp500_fundamentals.csv"
COVERAGE_PATH = DATA_DIR / "sp500_coverage.csv"
STATUS_PATH = DATA_DIR / "status.md"
MANIFEST_PATH = DATA_DIR / "manifest.json"

FMP_QUOTE_URL = "https://financialmodelingprep.com/stable/quote"

SCHEMA = "br05_market_v1.0"
REQUEST_DELAY_SECONDS = 0.26
TIMEOUT_SECONDS = 30
MAX_RETRIES = 4
MIN_WRITE_COVERAGE_PCT = 90.0


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def clean_symbol(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper().replace("/", ".")


def finite_positive(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or x <= 0:
        return None
    return x


def candidate_fmp_symbols(symbol: str) -> list[str]:
    out = [symbol]
    if "." in symbol:
        alt = symbol.replace(".", "-")
        if alt not in out:
            out.append(alt)
    return out


def safe_get_json(
    session: requests.Session,
    api_key: str,
    symbol: str,
) -> tuple[int, object | None]:
    delay = 1.0

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(
                FMP_QUOTE_URL,
                params={"symbol": symbol, "apikey": api_key},
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                return 0, None
            time.sleep(delay)
            delay *= 2
            continue

        if response.status_code == 200:
            try:
                return 200, response.json()
            except ValueError:
                return 200, None

        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt == MAX_RETRIES - 1:
                return response.status_code, None
            time.sleep(delay)
            delay *= 2
            continue

        return response.status_code, None

    return 0, None


def parse_quote_row(
    requested_ticker: str,
    fmp_symbol: str,
    payload,
    retrieved_at: str,
) -> dict | None:
    if not isinstance(payload, list) or not payload:
        return None

    row = payload[0]
    if not isinstance(row, dict):
        return None

    price = finite_positive(row.get("price"))
    market_cap = finite_positive(
        row.get("marketCap")
        if row.get("marketCap") is not None
        else row.get("mktCap")
    )

    raw_ts = row.get("timestamp")
    as_of = ""
    if raw_ts not in (None, ""):
        try:
            ts = float(raw_ts)
            if ts > 1_000_000_000:
                as_of = datetime.fromtimestamp(
                    ts, tz=timezone.utc
                ).replace(microsecond=0).isoformat()
        except (TypeError, ValueError, OverflowError):
            pass

    if price is None or market_cap is None:
        return None

    return {
        "ticker": requested_ticker,
        "market_price": price,
        "market_cap": market_cap,
        "market_data_as_of": as_of,
        "market_data_retrieved_at_utc": retrieved_at,
        "market_data_source": "FMP_STABLE_QUOTE_SINGLE",
        "market_data_source_symbol": fmp_symbol,
        "market_data_status": "PRESENT",
    }


def fetch_one(
    session: requests.Session,
    api_key: str,
    ticker: str,
    retrieved_at: str,
) -> tuple[dict | None, int]:
    last_status = 0

    for fmp_symbol in candidate_fmp_symbols(ticker):
        status, payload = safe_get_json(
            session=session,
            api_key=api_key,
            symbol=fmp_symbol,
        )
        last_status = status

        if status in (401, 402, 403):
            return None, status

        record = parse_quote_row(
            requested_ticker=ticker,
            fmp_symbol=fmp_symbol,
            payload=payload,
            retrieved_at=retrieved_at,
        )
        if record is not None:
            return record, status

        time.sleep(REQUEST_DELAY_SECONDS)

    return None, last_status


def coverage_pct(df: pd.DataFrame) -> float:
    if len(df) == 0:
        return 0.0
    ok = (
        df["market_price"].notna()
        & df["market_cap"].notna()
        & df["market_data_status"].eq("PRESENT")
    )
    return round(float(ok.mean() * 100), 1)


def merge_market_data(
    fundamentals: pd.DataFrame,
    market: pd.DataFrame,
) -> pd.DataFrame:
    cols = [
        "market_price",
        "market_cap",
        "market_data_as_of",
        "market_data_retrieved_at_utc",
        "market_data_source",
        "market_data_source_symbol",
        "market_data_status",
    ]

    base = fundamentals.drop(
        columns=[c for c in cols if c in fundamentals.columns],
        errors="ignore",
    ).copy()

    if market.empty:
        for c in cols:
            base[c] = None
        base["market_data_status"] = "MISSING"
        return base

    merged = base.merge(market, on="ticker", how="left")
    merged["market_data_status"] = (
        merged["market_data_status"].fillna("MISSING")
    )
    return merged


def update_coverage_file(df: pd.DataFrame) -> None:
    if COVERAGE_PATH.exists():
        cov = pd.read_csv(COVERAGE_PATH, low_memory=False)
    else:
        cov = df[["ticker", "name", "cik"]].copy()

    extra = pd.DataFrame(
        {
            "ticker": df["ticker"],
            "market_price_present": df["market_price"].notna(),
            "market_cap_present": df["market_cap"].notna(),
            "market_data_present": df["market_data_status"].eq("PRESENT"),
        }
    )

    for c in extra.columns:
        if c != "ticker" and c in cov.columns:
            cov = cov.drop(columns=[c])

    cov = cov.merge(extra, on="ticker", how="left")
    bridge.write_csv_atomic(COVERAGE_PATH, cov)


def update_status(df: pd.DataFrame) -> float:
    pct = coverage_pct(df)

    marker = "\n## V4.1 enrichment BR-05\n"
    base = (
        STATUS_PATH.read_text(encoding="utf-8")
        if STATUS_PATH.exists()
        else "# Investment OS Data Bridge — stato\n"
    )
    if marker in base:
        base = base.split(marker, 1)[0].rstrip() + "\n"

    as_of_present = round(
        float(df["market_data_as_of"].fillna("").ne("").mean() * 100), 1
    )

    section = f"""
## V4.1 enrichment BR-05

- Fonte market data: **FMP stable single-symbol quote**
- Prezzo + market cap direttamente disponibili: **{pct:.1f}%**
- Source timestamp disponibile: **{as_of_present:.1f}%**
- Market cap ricostruita da bridge shares: **NO**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
"""

    STATUS_PATH.write_text(
        base.rstrip() + "\n" + section.lstrip(),
        encoding="utf-8",
    )
    return pct


def main() -> int:
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato")

    api_key = os.getenv("FMP_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("FMP_API_KEY non configurata nell'ambiente")

    fundamentals = pd.read_csv(FUNDAMENTALS_PATH, low_memory=False)
    fundamentals["ticker"] = fundamentals["ticker"].map(clean_symbol)

    if fundamentals["ticker"].duplicated().any():
        raise SystemExit("Ticker duplicati nel fundamentals: BR-05 non eseguito")

    retrieved_at = now_iso()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "InvestmentOSDataBridge/1.0",
            "Accept": "application/json",
        }
    )

    records: list[dict] = []
    hard_error_status = None

    total = len(fundamentals)
    for i, ticker in enumerate(fundamentals["ticker"].tolist(), start=1):
        if not ticker:
            continue

        record, status = fetch_one(
            session=session,
            api_key=api_key,
            ticker=ticker,
            retrieved_at=retrieved_at,
        )

        if status in (401, 402, 403):
            hard_error_status = status
            print(
                f"FMP accesso/piano ha restituito HTTP {status} "
                f"alla richiesta {i}/{total}; stop sicuro."
            )
            break

        if record is not None:
            records.append(record)

        if i % 50 == 0 or i == total:
            print(
                f"BR-05 progress: {i}/{total}; "
                f"quote complete={len(records)}"
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    market = pd.DataFrame(records)

    if not market.empty:
        market = market.drop_duplicates("ticker", keep="last")

    enriched = merge_market_data(fundamentals, market)
    pct = coverage_pct(enriched)

    if hard_error_status is not None or pct < MIN_WRITE_COVERAGE_PCT:
        raise SystemExit(
            f"BR-05 NON scritto. Copertura={pct:.1f}%. "
            f"HTTP hard error={hard_error_status}. "
            "Nessun file data/current modificato."
        )

    bridge.write_csv_atomic(FUNDAMENTALS_PATH, enriched)
    update_coverage_file(enriched)
    pct = update_status(enriched)

    manifest = read_manifest()
    manifest["schema_version"] = "1.2"
    manifest["br05_market_enrichment"] = {
        "schema": SCHEMA,
        "updated_at_utc": now_iso(),
        "coverage_price_and_market_cap_pct": pct,
        "endpoint": FMP_QUOTE_URL,
        "source": "FMP_STABLE_QUOTE_SINGLE",
        "request_delay_seconds": REQUEST_DELAY_SECONDS,
        "rules": [
            "Market cap is accepted only when returned directly by FMP.",
            "Market cap is never reconstructed from bridge share count.",
            "Missing price/market cap remains MISSING, never zero.",
            "The API key is never written to repository files.",
            "This enrichment does not compute BQS, IOS, rankings, or recommendations.",
        ],
    }

    outputs = manifest.setdefault("outputs", {})
    for name in (
        "sp500_fundamentals.csv",
        "sp500_coverage.csv",
        "status.md",
    ):
        path = DATA_DIR / name
        if path.exists():
            outputs[name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }

    bridge.write_json_atomic(MANIFEST_PATH, manifest)

    print(
        f"OK — BR-05 completato. "
        f"Prezzo+market cap: {pct:.1f}% dell'universo."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
