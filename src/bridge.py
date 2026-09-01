#!/usr/bin/env python3
"""Investment OS Data Bridge.

Purpose
-------
Create small, auditable, Claude-friendly files for blind equity discovery using
free public sources:
  * State Street SPY daily holdings for the S&P 500 universe.
  * SEC Financial Statement Data Sets for normalized fundamentals.
  * SEC company_tickers.json for ticker -> CIK mapping.

The bridge does NOT rank stocks and does NOT issue investment recommendations.
It prepares source data only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "current"
ARCHIVE_DIR = ROOT / "data" / "archive"
MANIFEST_PATH = DATA_DIR / "manifest.json"

STATE_STREET_HOLDINGS_URL = os.getenv(
    "STATE_STREET_HOLDINGS_URL",
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
)
STATE_STREET_PRODUCT_URL = (
    "https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy"
)
SEC_DATASETS_PAGE = "https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Keep the automated access far below SEC's published 10 requests/second ceiling.
SEC_MIN_SECONDS_BETWEEN_REQUESTS = 0.35

ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
QUARTERLY_FORMS = {"10-Q"}

FLOW_METRICS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}

INSTANT_METRICS = {
    "assets": ["Assets"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
}

DEBT_DIRECT_TAGS = [
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebt",
]
DEBT_CURRENT_TAGS = [
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
]
DEBT_NONCURRENT_TAGS = [
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    "LongTermDebtNoncurrent",
]

ALL_RELEVANT_TAGS = sorted(
    set(
        sum(FLOW_METRICS.values(), [])
        + sum(INSTANT_METRICS.values(), [])
        + DEBT_DIRECT_TAGS
        + DEBT_CURRENT_TAGS
        + DEBT_NONCURRENT_TAGS
    )
)


class BridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuarterLink:
    year: int
    quarter: int
    label: str
    url: str

    @property
    def key(self) -> str:
        return f"{self.year}Q{self.quarter}"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def norm_col(value) -> str:
    text = norm_text(value).lower()
    text = text.replace("%", " percent ")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def normalize_ticker(value: str) -> str:
    """Normalize ticker for SEC mapping while preserving original separately."""
    t = norm_text(value).upper()
    # SEC convention commonly uses hyphens where data vendors use dots for share class.
    return t.replace(".", "-")


def read_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_csv_atomic(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def get_sec_contact_email() -> str:
    email = os.getenv("SEC_CONTACT_EMAIL", "").strip()
    if not email or "@" not in email:
        raise BridgeError(
            "Manca SEC_CONTACT_EMAIL. In GitHub crea il secret Actions 'SEC_CONTACT_EMAIL' "
            "con una tua email di contatto. Serve solo nel User-Agent dichiarato alla SEC e non viene salvata nei dati."
        )
    return email


class Downloader:
    def __init__(self):
        self.session = requests.Session()
        self.last_sec_request = 0.0
        self.sec_contact = get_sec_contact_email()

    def _sec_headers(self) -> dict:
        return {
            "User-Agent": f"InvestmentOSDataBridge/1.0 {self.sec_contact}",
            "Accept-Encoding": "gzip, deflate",
        }

    def _wait_for_sec(self):
        elapsed = time.monotonic() - self.last_sec_request
        if elapsed < SEC_MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(SEC_MIN_SECONDS_BETWEEN_REQUESTS - elapsed)

    def get_sec(self, url: str, *, stream: bool = False, timeout: int = 120) -> requests.Response:
        self._wait_for_sec()
        r = self.session.get(url, headers=self._sec_headers(), stream=stream, timeout=timeout)
        self.last_sec_request = time.monotonic()
        r.raise_for_status()
        return r

    def get_public(self, url: str, *, timeout: int = 120) -> requests.Response:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOSDataBridge/1.0)",
            "Accept": "*/*",
        }
        r = self.session.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r


def find_state_street_header(raw: pd.DataFrame) -> int:
    for i in range(min(60, len(raw))):
        cells = [norm_col(x) for x in raw.iloc[i].tolist()]
        has_ticker = any(c == "ticker" or c.endswith("_ticker") or "ticker" in c for c in cells)
        has_name = any(c in {"name", "security_name", "holding_name"} or "name" in c for c in cells)
        if has_ticker and has_name:
            return i
    raise BridgeError("Non trovo la riga intestazioni nel file State Street SPY.")


def choose_col(columns: Iterable[str], candidates: list[str], contains: list[str] | None = None) -> str | None:
    cols = list(columns)
    for c in candidates:
        if c in cols:
            return c
    for needle in contains or []:
        for c in cols:
            if needle in c:
                return c
    return None


def extract_as_of_from_raw(raw: pd.DataFrame) -> str | None:
    text = "\n".join(" | ".join(norm_text(v) for v in raw.iloc[i].tolist()) for i in range(min(25, len(raw))))
    patterns = [
        r"(?:as\s+of|holdings\s+as\s+of)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"(?:as\s+of|holdings\s+as\s+of)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(?:as\s+of|holdings\s+as\s+of)\s*[:\-]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            try:
                return pd.to_datetime(m.group(1)).date().isoformat()
            except Exception:
                pass
    return None


def parse_state_street_xlsx(content: bytes) -> tuple[pd.DataFrame, dict]:
    if not content.startswith(b"PK"):
        raise BridgeError("Il download State Street non sembra un file XLSX valido.")
    raw = pd.read_excel(io.BytesIO(content), header=None, engine="openpyxl")
    header_row = find_state_street_header(raw)
    df = pd.read_excel(io.BytesIO(content), header=header_row, engine="openpyxl")
    df.columns = [norm_col(c) or f"col_{i}" for i, c in enumerate(df.columns)]

    ticker_col = choose_col(df.columns, ["ticker", "ticker_symbol"], ["ticker"])
    name_col = choose_col(df.columns, ["name", "security_name", "holding_name"], ["name"])
    sector_col = choose_col(df.columns, ["sector", "gics_sector"], ["sector"])
    weight_col = choose_col(df.columns, ["weight", "weight_percent", "weight_percent_"], ["weight"])
    cusip_col = choose_col(df.columns, ["identifier", "cusip"], ["cusip", "identifier"])
    isin_col = choose_col(df.columns, ["isin"], ["isin"])
    asset_col = choose_col(df.columns, ["asset_class"], ["asset_class", "asset"])

    if not ticker_col or not name_col:
        raise BridgeError(f"Colonne State Street insufficienti. Colonne lette: {list(df.columns)}")

    out = pd.DataFrame({
        "ticker": df[ticker_col].map(norm_text),
        "name": df[name_col].map(norm_text),
    })
    out["ticker_sec"] = out["ticker"].map(normalize_ticker)
    if sector_col:
        out["sector"] = df[sector_col].map(norm_text)
    else:
        out["sector"] = ""
    if weight_col:
        out["weight"] = pd.to_numeric(df[weight_col], errors="coerce")
    else:
        out["weight"] = pd.NA
    out["identifier"] = df[cusip_col].map(norm_text) if cusip_col else ""
    out["isin"] = df[isin_col].map(norm_text) if isin_col else ""
    out["asset_class"] = df[asset_col].map(norm_text) if asset_col else ""

    out = out[(out["ticker"] != "") & (out["name"] != "")].copy()
    # Exclude obvious cash/collateral rows but do not guess about genuine equities.
    cash_mask = (
        out["ticker"].str.upper().isin({"USD", "CASH", "CASH_USD", "US DOLLAR"})
        | out["name"].str.upper().str.contains(r"\bUS DOLLAR\b|\bCASH\b", regex=True)
    )
    if asset_col:
        cash_mask = cash_mask | out["asset_class"].str.lower().str.contains("cash", na=False)
    excluded_cash = int(cash_mask.sum())
    out = out[~cash_mask].copy()

    out = out.drop_duplicates(subset=["ticker", "name"], keep="first").reset_index(drop=True)
    as_of = extract_as_of_from_raw(raw)
    meta = {
        "header_row_zero_based": int(header_row),
        "raw_rows_after_header": int(len(df)),
        "equity_like_rows": int(len(out)),
        "excluded_cash_or_obvious_non_equity_rows": excluded_cash,
        "data_as_of": as_of,
    }
    return out, meta


def download_state_street(d: Downloader) -> tuple[pd.DataFrame, dict]:
    r = d.get_public(STATE_STREET_HOLDINGS_URL)
    content = r.content
    df, meta = parse_state_street_xlsx(content)
    meta.update({
        "source": "State Street SPY daily holdings",
        "product_url": STATE_STREET_PRODUCT_URL,
        "download_url": STATE_STREET_HOLDINGS_URL,
        "downloaded_at": now_iso(),
        "sha256": sha256_bytes(content),
        "bytes": len(content),
    })
    return df, meta


def download_sec_ticker_map(d: Downloader) -> tuple[pd.DataFrame, dict]:
    r = d.get_sec(SEC_TICKERS_URL)
    content = r.content
    payload = r.json()
    rows = []
    values = payload.values() if isinstance(payload, dict) else payload
    for item in values:
        if not isinstance(item, dict):
            continue
        ticker = normalize_ticker(item.get("ticker", ""))
        cik = item.get("cik_str")
        if not ticker or cik is None:
            continue
        rows.append({
            "ticker_sec": ticker,
            "cik": str(int(cik)).zfill(10),
            "sec_title": norm_text(item.get("title", "")),
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["ticker_sec"], keep="first")
    meta = {
        "source": "SEC company_tickers.json",
        "url": SEC_TICKERS_URL,
        "downloaded_at": now_iso(),
        "sha256": sha256_bytes(content),
        "rows": int(len(df)),
    }
    return df, meta


def merge_universe_cik(universe: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
    out = universe.merge(ticker_map, how="left", on="ticker_sec")
    out["cik_status"] = out["cik"].notna().map({True: "PRESENT", False: "MISSING"})
    cols = [
        "ticker", "ticker_sec", "name", "sector", "weight", "identifier", "isin", "asset_class",
        "cik", "sec_title", "cik_status",
    ]
    return out[[c for c in cols if c in out.columns]].copy()


def discover_sec_quarters(d: Downloader) -> tuple[list[QuarterLink], dict]:
    r = d.get_sec(SEC_DATASETS_PAGE)
    soup = BeautifulSoup(r.text, "html.parser")
    found: dict[tuple[int, int], QuarterLink] = {}
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        m = re.fullmatch(r"(20\d{2})\s+Q([1-4])", text, flags=re.I)
        if not m:
            continue
        year, q = int(m.group(1)), int(m.group(2))
        url = urljoin(SEC_DATASETS_PAGE, a["href"])
        found[(year, q)] = QuarterLink(year, q, f"{year} Q{q}", url)
    quarters = sorted(found.values(), key=lambda x: (x.year, x.quarter))
    if not quarters:
        raise BridgeError("Non riesco a individuare i link trimestrali SEC nella pagina ufficiale.")
    meta = {
        "source": "SEC Financial Statement Data Sets index",
        "url": SEC_DATASETS_PAGE,
        "downloaded_at": now_iso(),
        "latest_available": quarters[-1].key,
        "quarters_found": len(quarters),
    }
    return quarters, meta


def download_to_file(d: Downloader, url: str, path: Path) -> tuple[str, int]:
    r = d.get_sec(url, stream=True, timeout=300)
    h = hashlib.sha256()
    n = 0
    with path.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            h.update(chunk)
            n += len(chunk)
    if not zipfile.is_zipfile(path):
        raise BridgeError(f"Il file SEC scaricato non è uno ZIP valido: {url}")
    return h.hexdigest(), n


def _read_tsv_from_zip(zf: zipfile.ZipFile, filename: str, **kwargs) -> pd.DataFrame:
    names = {n.lower(): n for n in zf.namelist()}
    actual = names.get(filename.lower())
    if not actual:
        raise BridgeError(f"{filename} non presente nello ZIP SEC. File presenti: {zf.namelist()[:20]}")
    with zf.open(actual) as f:
        return pd.read_csv(f, sep="\t", low_memory=False, **kwargs)


def load_submissions_from_zips(zip_infos: list[tuple[QuarterLink, Path]]) -> pd.DataFrame:
    frames = []
    for q, path in zip_infos:
        with zipfile.ZipFile(path) as zf:
            sub = _read_tsv_from_zip(zf, "sub.txt", dtype=str)
        required = {"adsh", "cik", "name", "form", "period", "filed"}
        missing = required - set(sub.columns)
        if missing:
            raise BridgeError(f"SUB SEC {q.key}: mancano colonne {sorted(missing)}")
        sub["cik"] = sub["cik"].map(lambda x: str(int(float(x))).zfill(10) if norm_text(x) else "")
        sub["sec_source_quarter"] = q.key
        frames.append(sub)
    return pd.concat(frames, ignore_index=True, sort=False)


def choose_latest_filings(sub: pd.DataFrame, universe_ciks: set[str]) -> pd.DataFrame:
    work = sub[sub["cik"].isin(universe_ciks)].copy()
    work["form"] = work["form"].astype(str).str.upper().str.strip()
    work = work[work["form"].isin(ANNUAL_FORMS | QUARTERLY_FORMS)].copy()
    work["filed_num"] = pd.to_numeric(work["filed"], errors="coerce")
    work["period_num"] = pd.to_numeric(work["period"], errors="coerce")
    work = work.sort_values(["cik", "filed_num", "period_num"], ascending=[True, False, False])

    annual = work[work["form"].isin(ANNUAL_FORMS)].drop_duplicates("cik", keep="first").copy()
    annual["filing_kind"] = "annual"
    quarterly = work[work["form"].isin(QUARTERLY_FORMS)].drop_duplicates("cik", keep="first").copy()
    quarterly["filing_kind"] = "quarterly"
    selected = pd.concat([annual, quarterly], ignore_index=True, sort=False)
    return selected


def scan_relevant_nums(zip_infos: list[tuple[QuarterLink, Path]], adsh_set: set[str]) -> pd.DataFrame:
    frames = []
    for q, path in zip_infos:
        with zipfile.ZipFile(path) as zf:
            names = {n.lower(): n for n in zf.namelist()}
            actual = names.get("num.txt")
            if not actual:
                raise BridgeError(f"num.txt non presente in {q.key}")
            with zf.open(actual) as f:
                reader = pd.read_csv(f, sep="\t", dtype=str, low_memory=False, chunksize=250_000)
                for chunk in reader:
                    if "adsh" not in chunk or "tag" not in chunk:
                        raise BridgeError(f"NUM SEC {q.key}: colonne adsh/tag assenti")
                    mask = chunk["adsh"].isin(adsh_set) & chunk["tag"].isin(ALL_RELEVANT_TAGS)
                    if "coreg" in chunk.columns:
                        mask &= chunk["coreg"].fillna("").eq("")
                    if "segments" in chunk.columns:
                        mask &= chunk["segments"].fillna("").eq("")
                    part = chunk.loc[mask].copy()
                    if len(part):
                        part["sec_source_quarter"] = q.key
                        frames.append(part)
    if not frames:
        return pd.DataFrame(columns=["adsh", "tag", "ddate", "qtrs", "uom", "value"])
    out = pd.concat(frames, ignore_index=True, sort=False)
    out["value_num"] = pd.to_numeric(out.get("value"), errors="coerce")
    out["ddate_num"] = pd.to_numeric(out.get("ddate"), errors="coerce")
    out["qtrs_num"] = pd.to_numeric(out.get("qtrs"), errors="coerce")
    return out


def _pick_tag_values(df: pd.DataFrame, adsh: str, tags: list[str], qtrs: int, uom: str | None) -> tuple[float | None, str, str, float | None, str]:
    if df.empty:
        return None, "", "", None, ""
    x = df[df["adsh"].eq(adsh) & df["tag"].isin(tags) & df["qtrs_num"].eq(qtrs)].copy()
    if uom and "uom" in x.columns:
        unit_mask = x["uom"].astype(str).str.lower().eq(uom.lower())
        if unit_mask.any():
            x = x[unit_mask]
    x = x[x["value_num"].notna() & x["ddate_num"].notna()].copy()
    if x.empty:
        return None, "", "", None, ""
    priority = {tag: i for i, tag in enumerate(tags)}
    x["tag_priority"] = x["tag"].map(priority).fillna(9999)
    x = x.sort_values(["tag_priority", "ddate_num"], ascending=[True, False])
    # Prefer the first candidate tag that exists; then current/prior dates within that same tag.
    best_tag = x.iloc[0]["tag"]
    y = x[x["tag"].eq(best_tag)].sort_values("ddate_num", ascending=False)
    dates = list(dict.fromkeys(y["ddate_num"].dropna().astype(int).tolist()))
    current_date = dates[0] if dates else None
    prior_date = dates[1] if len(dates) > 1 else None
    cur_rows = y[y["ddate_num"].eq(current_date)] if current_date else y.iloc[0:0]
    current = float(cur_rows.iloc[0]["value_num"]) if len(cur_rows) else None
    prior = None
    if prior_date:
        pr = y[y["ddate_num"].eq(prior_date)]
        if len(pr):
            prior = float(pr.iloc[0]["value_num"])
    return current, best_tag, str(int(current_date)) if current_date else "", prior, str(int(prior_date)) if prior_date else ""


def _pick_instant(df: pd.DataFrame, adsh: str, tags: list[str], uom: str = "USD") -> tuple[float | None, str, str]:
    x = df[df["adsh"].eq(adsh) & df["tag"].isin(tags) & df["qtrs_num"].eq(0)].copy()
    if "uom" in x.columns:
        unit_mask = x["uom"].astype(str).str.lower().eq(uom.lower())
        if unit_mask.any():
            x = x[unit_mask]
    x = x[x["value_num"].notna() & x["ddate_num"].notna()].copy()
    if x.empty:
        return None, "", ""
    priority = {tag: i for i, tag in enumerate(tags)}
    x["tag_priority"] = x["tag"].map(priority).fillna(9999)
    x = x.sort_values(["tag_priority", "ddate_num"], ascending=[True, False])
    best_tag = x.iloc[0]["tag"]
    y = x[x["tag"].eq(best_tag)].sort_values("ddate_num", ascending=False)
    row = y.iloc[0]
    return float(row["value_num"]), best_tag, str(int(row["ddate_num"]))


def _pick_debt(df: pd.DataFrame, adsh: str) -> tuple[float | None, str, str]:
    direct, tag, date = _pick_instant(df, adsh, DEBT_DIRECT_TAGS, "USD")
    if direct is not None:
        return direct, tag, date
    cur, cur_tag, cur_date = _pick_instant(df, adsh, DEBT_CURRENT_TAGS, "USD")
    noncur, noncur_tag, noncur_date = _pick_instant(df, adsh, DEBT_NONCURRENT_TAGS, "USD")
    if cur is None and noncur is None:
        return None, "", ""
    total = (cur or 0.0) + (noncur or 0.0)
    tags = "+".join(t for t in [cur_tag, noncur_tag] if t)
    dates = "+".join(d for d in [cur_date, noncur_date] if d)
    return total, tags, dates


def pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return current / prior - 1.0


def safe_ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def build_fundamentals(universe: pd.DataFrame, selected: pd.DataFrame, nums: pd.DataFrame, sec_quarters: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_by = {(r["cik"], r["filing_kind"]): r for _, r in selected.iterrows()}
    rows = []

    for _, u in universe.iterrows():
        cik = norm_text(u.get("cik"))
        annual = selected_by.get((cik, "annual")) if cik else None
        quarterly = selected_by.get((cik, "quarterly")) if cik else None
        row = {
            "ticker": u.get("ticker", ""),
            "ticker_sec": u.get("ticker_sec", ""),
            "name": u.get("name", ""),
            "sector": u.get("sector", ""),
            "weight": u.get("weight", pd.NA),
            "cik": cik,
            "sic": "",
            "annual_form": "",
            "annual_period": "",
            "annual_filed": "",
            "annual_adsh": "",
            "latest_10q_period": "",
            "latest_10q_filed": "",
            "sec_quarters_used": ";".join(sec_quarters),
        }
        if annual is not None:
            row.update({
                "sic": norm_text(annual.get("sic", "")),
                "annual_form": norm_text(annual.get("form", "")),
                "annual_period": norm_text(annual.get("period", "")),
                "annual_filed": norm_text(annual.get("filed", "")),
                "annual_adsh": norm_text(annual.get("adsh", "")),
            })
        if quarterly is not None:
            row.update({
                "latest_10q_period": norm_text(quarterly.get("period", "")),
                "latest_10q_filed": norm_text(quarterly.get("filed", "")),
            })

        adsh = row["annual_adsh"]
        # Annual flow metrics (current + prior comparative value if present in same filing).
        for metric, tags in FLOW_METRICS.items():
            uom = "shares" if metric == "diluted_shares" else "USD"
            cur, tag, ddate, prior, prior_ddate = _pick_tag_values(nums, adsh, tags, 4, uom) if adsh else (None, "", "", None, "")
            row[f"annual_{metric}"] = cur
            row[f"annual_{metric}_tag"] = tag
            row[f"annual_{metric}_date"] = ddate
            row[f"prior_{metric}"] = prior
            row[f"prior_{metric}_date"] = prior_ddate

        for metric, tags in INSTANT_METRICS.items():
            val, tag, ddate = _pick_instant(nums, adsh, tags, "USD") if adsh else (None, "", "")
            row[f"annual_{metric}"] = val
            row[f"annual_{metric}_tag"] = tag
            row[f"annual_{metric}_date"] = ddate

        debt, debt_tag, debt_date = _pick_debt(nums, adsh) if adsh else (None, "", "")
        row["annual_debt"] = debt
        row["annual_debt_tag"] = debt_tag
        row["annual_debt_date"] = debt_date

        cfo = row.get("annual_operating_cash_flow")
        capex = row.get("annual_capex")
        row["annual_fcf"] = (cfo - abs(capex)) if cfo is not None and capex is not None else None
        row["revenue_yoy"] = pct_change(row.get("annual_revenue"), row.get("prior_revenue"))
        row["net_income_yoy"] = pct_change(row.get("annual_net_income"), row.get("prior_net_income"))
        row["diluted_shares_yoy"] = pct_change(row.get("annual_diluted_shares"), row.get("prior_diluted_shares"))
        row["operating_margin"] = safe_ratio(row.get("annual_operating_income"), row.get("annual_revenue"))
        row["net_margin"] = safe_ratio(row.get("annual_net_income"), row.get("annual_revenue"))
        row["fcf_margin"] = safe_ratio(row.get("annual_fcf"), row.get("annual_revenue"))
        row["roe_simple"] = safe_ratio(row.get("annual_net_income"), row.get("annual_equity"))
        row["debt_to_equity"] = safe_ratio(row.get("annual_debt"), row.get("annual_equity"))

        # Coverage is descriptive only. It is NOT a quality score and must not penalize sector N/A metrics.
        core = ["annual_revenue", "annual_net_income", "annual_assets", "annual_equity", "annual_operating_cash_flow", "annual_diluted_shares"]
        ext = core + ["annual_capex", "annual_debt"]
        core_present = sum(pd.notna(row.get(c)) for c in core)
        ext_present = sum(pd.notna(row.get(c)) for c in ext)
        row["core_metric_coverage_pct"] = round(100 * core_present / len(core), 1)
        row["extended_metric_coverage_pct"] = round(100 * ext_present / len(ext), 1)
        flags = []
        if not cik:
            flags.append("MISSING_CIK")
        if annual is None:
            flags.append("MISSING_ANNUAL_FILING_IN_BULK_WINDOW")
        for c in core:
            if pd.isna(row.get(c)):
                flags.append("MISSING_" + c.replace("annual_", "").upper())
        row["data_quality_flags"] = ";".join(flags) if flags else "OK"
        row["data_status"] = "PRESENT" if not flags else "PARTIAL"
        rows.append(row)

    fundamentals = pd.DataFrame(rows)
    coverage = fundamentals[[
        "ticker", "name", "sector", "cik", "annual_period", "annual_filed",
        "core_metric_coverage_pct", "extended_metric_coverage_pct", "data_status", "data_quality_flags"
    ]].copy()
    return fundamentals, coverage


def archive_current(reason: str) -> str | None:
    files = [DATA_DIR / n for n in ["sp500_universe.csv", "sp500_fundamentals.csv", "sp500_coverage.csv", "manifest.json", "status.md"]]
    existing = [p for p in files if p.exists()]
    if not existing:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = ARCHIVE_DIR / f"{stamp}_{re.sub(r'[^A-Za-z0-9_-]+', '_', reason)}"
    dest.mkdir(parents=True, exist_ok=True)
    for p in existing:
        shutil.copy2(p, dest / p.name)
    return str(dest.relative_to(ROOT))


def generate_claude_sources(repo_slug: str | None) -> str:
    if repo_slug:
        base = f"https://raw.githubusercontent.com/{repo_slug}/main/data/current"
        links = {
            "Universe": f"{base}/sp500_universe.csv",
            "Fundamentals": f"{base}/sp500_fundamentals.csv",
            "Coverage": f"{base}/sp500_coverage.csv",
            "Manifest": f"{base}/manifest.json",
            "Status": f"{base}/status.md",
        }
        body = "\n".join(f"- **{k}:** {v}" for k, v in links.items())
    else:
        body = (
            "Il workflow non ha fornito `GITHUB_REPOSITORY`. Dopo il primo run GitHub Actions, "
            "questo file verrà rigenerato con i link raw del repository."
        )
    return f"""# Investment OS Data Bridge — sorgenti per Claude\n\n{body}\n\n## Regole d'uso\n\n- Questi file sono dati di discovery, non raccomandazioni.\n- Verificare `manifest.json` e `status.md` prima di ogni screening.\n- `MISSING` non è zero.\n- Banche, assicurazioni, REIT e altri settori speciali richiedono metriche settoriali.\n- Per i finalisti, riconciliare sempre i dati con l'ultimo filing SEC/Investor Relations.\n- Non usare questi file per bypassare il Decision Gate o l'IPS.\n"""


def write_status(universe: pd.DataFrame, fundamentals: pd.DataFrame | None, manifest: dict) -> None:
    cik_pct = float(universe["cik"].notna().mean() * 100) if len(universe) and "cik" in universe else 0.0
    if fundamentals is not None and len(fundamentals):
        annual_pct = float((fundamentals["annual_adsh"].astype(str) != "").mean() * 100)
        core_90 = float((fundamentals["core_metric_coverage_pct"] >= 90).mean() * 100)
        fline = f"- Società con filing annuale individuato: **{annual_pct:.1f}%**\n- Società con >=90% core metric coverage: **{core_90:.1f}%**"
    else:
        fline = "- Fondamentali: non ricostruiti in questo run (riuso dello snapshot esistente, se presente)."
    text = f"""# Investment OS Data Bridge — stato\n\nAggiornato: **{manifest.get('updated_at_utc', '')}**\n\n- Righe universo equity-like: **{len(universe)}**\n- Ticker con CIK SEC mappato: **{cik_pct:.1f}%**\n{fline}\n- Ultimo SEC Financial Statement Data Set disponibile: **{manifest.get('sec', {}).get('latest_available_quarter', 'N/D')}**\n- Fondamentali costruiti usando trimestri: **{', '.join(manifest.get('sec', {}).get('quarters_used', [])) or 'N/D'}**\n\n## Importante\n\nLa copertura qui è una misura tecnica, non un BQS. Metriche non appropriate a un settore possono essere `NOT_APPLICABLE` nel successivo processo di analisi. Prima di BUY/ADD i finalisti devono essere verificati contro gli ultimi filing e fonti primarie.\n"""
    (DATA_DIR / "status.md").write_text(text, encoding="utf-8")


def refresh(mode: str, quarter_count: int, force_sec: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    previous = read_manifest()
    d = Downloader()

    print("[1/5] Scarico holdings SPY da State Street...")
    universe_raw, ss_meta = download_state_street(d)
    print(f"      Righe equity-like: {len(universe_raw)}")

    print("[2/5] Scarico mappa ticker->CIK dalla SEC...")
    ticker_map, ticker_meta = download_sec_ticker_map(d)
    universe = merge_universe_cik(universe_raw, ticker_map)

    print("[3/5] Individuo l'ultimo SEC Financial Statement Data Set...")
    quarters, sec_index_meta = discover_sec_quarters(d)
    selected_quarters = quarters[-quarter_count:]
    latest_key = quarters[-1].key

    existing_fund = DATA_DIR / "sp500_fundamentals.csv"
    prev_latest = previous.get("sec", {}).get("latest_available_quarter")
    rebuild_sec = mode == "full" or force_sec or not existing_fund.exists() or prev_latest != latest_key
    if mode == "universe":
        rebuild_sec = False

    archived = None
    if rebuild_sec and existing_fund.exists():
        archived = archive_current(f"before_{latest_key}")

    fundamentals = None
    coverage = None
    sec_download_meta = []

    if rebuild_sec:
        print(f"[4/5] Nuovo/forzato refresh SEC: uso gli ultimi {len(selected_quarters)} trimestri...")
        with tempfile.TemporaryDirectory(prefix="investment_os_sec_") as td:
            td_path = Path(td)
            zip_infos: list[tuple[QuarterLink, Path]] = []
            for q in selected_quarters:
                path = td_path / f"{q.key}.zip"
                print(f"      Scarico {q.label} ...")
                sha, nbytes = download_to_file(d, q.url, path)
                zip_infos.append((q, path))
                sec_download_meta.append({"quarter": q.key, "url": q.url, "sha256": sha, "bytes": nbytes})

            subs = load_submissions_from_zips(zip_infos)
            universe_ciks = set(universe["cik"].dropna().astype(str))
            selected_filings = choose_latest_filings(subs, universe_ciks)
            adsh_set = set(selected_filings["adsh"].dropna().astype(str))
            print(f"      Filing selezionati: {len(selected_filings)}; scansione NUM sui tag utili...")
            nums = scan_relevant_nums(zip_infos, adsh_set)
            fundamentals, coverage = build_fundamentals(
                universe,
                selected_filings,
                nums,
                [q.key for q in selected_quarters],
            )
    else:
        print("[4/5] SEC bulk invariato: evito download massivo e riuso i fondamentali esistenti.")
        if existing_fund.exists():
            fundamentals = pd.read_csv(existing_fund, low_memory=False)
            cov_path = DATA_DIR / "sp500_coverage.csv"
            coverage = pd.read_csv(cov_path, low_memory=False) if cov_path.exists() else None

    print("[5/5] Scrivo output piccoli e verificabili...")
    write_csv_atomic(DATA_DIR / "sp500_universe.csv", universe)
    if rebuild_sec and fundamentals is not None:
        write_csv_atomic(DATA_DIR / "sp500_fundamentals.csv", fundamentals)
        write_csv_atomic(DATA_DIR / "sp500_coverage.csv", coverage)

    manifest = {
        "schema_version": "1.0",
        "updated_at_utc": now_iso(),
        "mode": mode,
        "fundamentals_rebuilt_this_run": bool(rebuild_sec),
        "state_street": ss_meta,
        "sec_ticker_map": ticker_meta,
        "sec": {
            "index": sec_index_meta,
            "latest_available_quarter": latest_key,
            "quarters_used": [q.key for q in selected_quarters] if rebuild_sec else previous.get("sec", {}).get("quarters_used", []),
            "quarter_downloads": sec_download_meta if rebuild_sec else previous.get("sec", {}).get("quarter_downloads", []),
            "fair_access_note": "Declared User-Agent; scripted downloads intentionally kept far below 10 requests/second.",
        },
        "universe": {
            "rows": int(len(universe)),
            "cik_mapped": int(universe["cik"].notna().sum()),
            "cik_mapping_pct": round(float(universe["cik"].notna().mean() * 100), 2) if len(universe) else 0,
        },
        "archive_created": archived,
        "outputs": {},
        "methodology_notes": [
            "The bridge prepares data only; it does not compute BQS/IOS or recommendations.",
            "SEC Financial Statement Data Sets are as-filed primary-statement data and are quarterly; final candidates require reconciliation to latest filings.",
            "Coverage percentages are technical availability measures, not investment-quality scores.",
            "Missing data must not be converted to zero; sector-specific metrics may be NOT_APPLICABLE downstream.",
        ],
    }
    repo_slug = os.getenv("GITHUB_REPOSITORY", "").strip() or None
    (DATA_DIR / "claude_sources.md").write_text(generate_claude_sources(repo_slug), encoding="utf-8")

    # Temporarily write manifest, then compute hashes for every output except manifest itself.
    write_json_atomic(MANIFEST_PATH, manifest)
    for name in ["sp500_universe.csv", "sp500_fundamentals.csv", "sp500_coverage.csv", "claude_sources.md"]:
        p = DATA_DIR / name
        if p.exists():
            manifest["outputs"][name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    write_status(universe, fundamentals, manifest)
    manifest["outputs"]["status.md"] = {
        "sha256": sha256_file(DATA_DIR / "status.md"),
        "bytes": (DATA_DIR / "status.md").stat().st_size,
    }
    write_json_atomic(MANIFEST_PATH, manifest)

    print("OK — Data Bridge aggiornato.")
    print(f"Universe rows: {len(universe)} | CIK mapping: {manifest['universe']['cik_mapping_pct']}% | SEC latest: {latest_key}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Investment OS Data Bridge")
    parser.add_argument(
        "--mode",
        choices=["auto", "universe", "full"],
        default="auto",
        help="auto: universe weekly + SEC rebuild only when a new quarter appears; universe: no SEC bulk; full: force full rebuild",
    )
    parser.add_argument("--quarters", type=int, default=4, help="Numero di SEC quarterly data sets da usare per trovare i filing più recenti (default 4)")
    parser.add_argument("--force-sec", action="store_true", help="Forza il rebuild SEC anche se il trimestre disponibile non è cambiato")
    args = parser.parse_args()
    if not (1 <= args.quarters <= 8):
        parser.error("--quarters deve essere tra 1 e 8")
    try:
        refresh(args.mode, args.quarters, args.force_sec)
        return 0
    except BridgeError as e:
        print(f"ERRORE DATA BRIDGE: {e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"ERRORE RETE: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ERRORE IMPREVISTO: {type(e).__name__}: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
