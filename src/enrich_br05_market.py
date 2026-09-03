#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-05 market data enrichment.

Primary source:
- Nasdaq public stock screener (bulk, one request).

Fallback:
- Financial Modeling Prep stable single-symbol quote only for Nasdaq rows
  that are missing or incomplete.

Integrity rules:
- Market cap is accepted only when returned directly by Nasdaq or FMP.
- Market cap is NEVER reconstructed from bridge share counts.
- FMP_API_KEY is read only from the environment and is never printed/written.
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

NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks"
FMP_QUOTE_URL = "https://financialmodelingprep.com/stable/quote"

NASDAQ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/",
}

SCHEMA = "br05_market_v2.0"
TIMEOUT_SECONDS = 45
FMP_REQUEST_DELAY_SECONDS = 0.35
MAX_FMP_RETRIES = 3
MIN_WRITE_COVERAGE_PCT = 98.0


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


def symbol_variants(symbol: str) -> list[str]:
    variants = [symbol]
    if "." in symbol:
        variants.append(symbol.replace(".", "-"))
    if "-" in symbol:
        variants.append(symbol.replace("-", "."))
    return list(dict.fromkeys(variants))


def finite_positive(value):
    if value is None or pd.isna(value):
        return None

    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None

    try:
        x = float(text)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(x) or x <= 0:
        return None
    return x


def fetch_nasdaq_bulk(
    session: requests.Session,
    retrieved_at: str,
) -> tuple[dict[str, dict], dict]:
    response = session.get(
        NASDAQ_URL,
        headers=NASDAQ_HEADERS,
        params={
            "tableonly": "true",
            "limit": "10000",
            "offset": "0",
            "download": "true",
        },
        timeout=TIMEOUT_SECONDS,
    )

    meta = {
        "http_status": response.status_code,
        "rows_returned": 0,
        "retrieved_at_utc": retrieved_at,
    }

    if response.status_code != 200:
        return {}, meta

    try:
        payload = response.json()
    except ValueError:
        return {}, meta

    rows = ((payload or {}).get("data") or {}).get("rows") or []
    meta["rows_returned"] = len(rows)

    market: dict[str, dict] = {}

    for row in rows:
        symbol = clean_symbol(row.get("symbol"))
        if not symbol:
            continue

        price = finite_positive(
            row.get("lastsale")
            if row.get("lastsale") is not None
            else row.get("lastSalePrice")
        )
        market_cap = finite_positive(row.get("marketCap"))

        market[symbol] = {
            "price": price,
            "market_cap": market_cap,
        }

    return market, meta


def candidate_fmp_symbols(symbol: str) -> list[str]:
    out = [symbol]
    if "." in symbol:
        alt = symbol.replace(".", "-")
        if alt not in out:
            out.append(alt)
    return out


def fetch_fmp_quote(
    session: requests.Session,
    api_key: str,
    requested_ticker: str,
    retrieved_at: str,
) -> tuple[dict | None, int]:
    last_status = 0

    for fmp_symbol in candidate_fmp_symbols(requested_ticker):
        backoff = 1.0

        for attempt in range(MAX_FMP_RETRIES):
            try:
                response = session.get(
                    FMP_QUOTE_URL,
                    params={"symbol": fmp_symbol, "apikey": api_key},
                    timeout=30,
                )
            except requests.RequestException:
                if attempt == MAX_FMP_RETRIES - 1:
                    break
                time.sleep(backoff)
                backoff *= 2
                continue

            last_status = response.status_code

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    payload = None

                if isinstance(payload, list) and payload:
                    row = payload[0]
                    price = finite_positive(row.get("price"))
                    market_cap = finite_positive(
                        row.get("marketCap")
                        if row.get("marketCap") is not None
                        else row.get("mktCap")
                    )

                    as_of = ""
                    raw_ts = row.get("timestamp")
                    if raw_ts not in (None, ""):
                        try:
                            ts = float(raw_ts)
                            if ts > 1_000_000_000:
                                as_of = datetime.fromtimestamp(
                                    ts, tz=timezone.utc
                                ).replace(microsecond=0).isoformat()
                        except (TypeError, ValueError, OverflowError):
                            pass

                    if price is not None and market_cap is not None:
                        return {
                            "ticker": requested_ticker,
                            "market_price": price,
                            "market_cap": market_cap,
                            "market_data_as_of": as_of,
                            "market_data_retrieved_at_utc": retrieved_at,
                            "market_data_source": "FMP_STABLE_QUOTE_SINGLE",
                            "market_data_source_symbol": fmp_symbol,
                            "market_data_as_of_status": (
                                "SOURCE_TIMESTAMP"
                                if as_of
                                else "RETRIEVAL_TIME_ONLY"
                            ),
                            "market_data_status": "PRESENT",
                        }, response.status_code

                break

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == MAX_FMP_RETRIES - 1:
                    break
                time.sleep(backoff)
                backoff *= 2
                continue

            break

        time.sleep(FMP_REQUEST_DELAY_SECONDS)

    return None, last_status


def build_market_frame(
    fundamentals: pd.DataFrame,
    nasdaq_market: dict[str, dict],
    api_key: str,
    retrieved_at: str,
) -> tuple[pd.DataFrame, dict]:
    records: list[dict] = []
    fallback_needed: list[str] = []

    for ticker in fundamentals["ticker"].tolist():
        nasdaq_record = None
        matched_symbol = ""

        for candidate in symbol_variants(ticker):
            candidate_row = nasdaq_market.get(candidate)
            if candidate_row is not None:
                nasdaq_record = candidate_row
                matched_symbol = candidate
                break

        if (
            nasdaq_record is not None
            and nasdaq_record.get("price") is not None
            and nasdaq_record.get("market_cap") is not None
        ):
            records.append(
                {
                    "ticker": ticker,
                    "market_price": nasdaq_record["price"],
                    "market_cap": nasdaq_record["market_cap"],
                    "market_data_as_of": "",
                    "market_data_retrieved_at_utc": retrieved_at,
                    "market_data_source": "NASDAQ_PUBLIC_SCREENER",
                    "market_data_source_symbol": matched_symbol,
                    "market_data_as_of_status": "RETRIEVAL_TIME_ONLY",
                    "market_data_status": "PRESENT",
                }
            )
        else:
            fallback_needed.append(ticker)

    fallback_meta = {
        "requested": len(fallback_needed),
        "completed": 0,
        "http_statuses": {},
    }

    if fallback_needed and api_key:
        fmp_session = requests.Session()
        fmp_session.headers.update(
            {
                "User-Agent": "InvestmentOSDataBridge/1.0",
                "Accept": "application/json",
            }
        )

        for ticker in fallback_needed:
            record, status = fetch_fmp_quote(
                session=fmp_session,
                api_key=api_key,
                requested_ticker=ticker,
                retrieved_at=retrieved_at,
            )

            key = str(status)
            fallback_meta["http_statuses"][key] = (
                fallback_meta["http_statuses"].get(key, 0) + 1
            )

            if record is not None:
                records.append(record)
                fallback_meta["completed"] += 1

    return pd.DataFrame(records), fallback_meta


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
        "market_data_as_of_status",
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

    market = market.drop_duplicates("ticker", keep="last")
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

    counts = (
        df["market_data_source"]
        .fillna("MISSING")
        .value_counts()
        .to_dict()
    )

    section = f"""
## V4.1 enrichment BR-05

- Fonte primaria market data: **Nasdaq public stock screener**
- Fallback: **FMP stable single-symbol quote, solo per righe mancanti/incomplete**
- Prezzo + market cap direttamente disponibili: **{pct:.1f}%**
- Market cap ricostruita da bridge shares: **NO**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
- Source counts: **{json.dumps(counts, sort_keys=True)}**
"""

    STATUS_PATH.write_text(
        base.rstrip() + "\n" + section.lstrip(),
        encoding="utf-8",
    )
    return pct


def main() -> int:
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato")

    fundamentals = pd.read_csv(FUNDAMENTALS_PATH, low_memory=False)
    fundamentals["ticker"] = fundamentals["ticker"].map(clean_symbol)

    if fundamentals["ticker"].duplicated().any():
        raise SystemExit("Ticker duplicati nel fundamentals: BR-05 non eseguito")

    retrieved_at = now_iso()

    nasdaq_session = requests.Session()
    nasdaq_market, nasdaq_meta = fetch_nasdaq_bulk(
        session=nasdaq_session,
        retrieved_at=retrieved_at,
    )

    if nasdaq_meta["http_status"] != 200 or not nasdaq_market:
        raise SystemExit(
            "BR-05 NON scritto: Nasdaq bulk non disponibile. "
            "Nessun file data/current modificato."
        )

    api_key = os.getenv("FMP_API_KEY", "").strip()

    market, fallback_meta = build_market_frame(
        fundamentals=fundamentals,
        nasdaq_market=nasdaq_market,
        api_key=api_key,
        retrieved_at=retrieved_at,
    )

    enriched = merge_market_data(fundamentals, market)
    pct = coverage_pct(enriched)

    if pct < MIN_WRITE_COVERAGE_PCT:
        raise SystemExit(
            f"BR-05 NON scritto. Copertura={pct:.1f}% "
            f"< {MIN_WRITE_COVERAGE_PCT:.1f}%. "
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
        "primary_source": "NASDAQ_PUBLIC_SCREENER",
        "primary_endpoint": NASDAQ_URL,
        "nasdaq": nasdaq_meta,
        "fallback_source": "FMP_STABLE_QUOTE_SINGLE",
        "fallback_endpoint": FMP_QUOTE_URL,
        "fallback": fallback_meta,
        "rules": [
            "Market cap is accepted only when returned directly by Nasdaq or FMP.",
            "Market cap is never reconstructed from bridge share count.",
            "Missing price/market cap remains MISSING, never zero.",
            "FMP is used only as fallback for Nasdaq missing/incomplete rows.",
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
    print(
        "Nasdaq rows:",
        nasdaq_meta["rows_returned"],
        "| FMP fallback requested:",
        fallback_meta["requested"],
        "| completed:",
        fallback_meta["completed"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
