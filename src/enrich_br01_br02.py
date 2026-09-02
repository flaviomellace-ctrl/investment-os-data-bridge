#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-01 + BR-02 enrichment.

BR-01
-----
Adds up to four annual fiscal-year observations for:
- revenue
- operating income
- net income
- operating cash flow
- capex
- diluted shares
- equity

and derives conservative 3-year CAGRs where mathematically meaningful.

BR-02
-----
Adds stock-based compensation (SBC) from SEC XBRL tags, preferring
ShareBasedCompensation because it is the amount added back in operating cash flow.

This script enriches the existing data/current/sp500_fundamentals.csv produced by
src/bridge.py. It never converts missing data to zero and it never ranks stocks.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import bridge


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "current"
MANIFEST_PATH = DATA_DIR / "manifest.json"
FUNDAMENTALS_PATH = DATA_DIR / "sp500_fundamentals.csv"
COVERAGE_PATH = DATA_DIR / "sp500_coverage.csv"
STATUS_PATH = DATA_DIR / "status.md"

HISTORY_YEARS = 4
SEC_QUARTERS = 16

SBC_TAGS = [
    "ShareBasedCompensation",
    "AllocatedShareBasedCompensationExpense",
    "ShareBasedCompensationArrangementByShareBasedPaymentAwardCompensationCost",
    "EmployeeServiceShareBasedCompensationAllocationOfRecognizedPeriodCostsCapitalizedAmount",
]

FLOW_METRICS = dict(bridge.FLOW_METRICS)
HISTORY_INSTANT_METRICS = {
    "equity": bridge.INSTANT_METRICS["equity"],
}

RELEVANT_TAGS = sorted(
    set(
        sum(FLOW_METRICS.values(), [])
        + sum(HISTORY_INSTANT_METRICS.values(), [])
        + SBC_TAGS
    )
)

ENRICHMENT_SCHEMA = "br01_br02_v1.0"


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


def write_manifest(payload: dict) -> None:
    bridge.write_json_atomic(MANIFEST_PATH, payload)


def needs_enrichment(df: pd.DataFrame, manifest: dict, latest_key: str) -> bool:
    required_cols = {
        "fy_minus_2_revenue",
        "fy_minus_3_revenue",
        "fy_minus_2_operating_income",
        "fy_minus_3_operating_income",
        "fy_minus_2_operating_cash_flow",
        "fy_minus_3_operating_cash_flow",
        "fy_minus_2_capex",
        "fy_minus_3_capex",
        "fy_minus_2_diluted_shares",
        "fy_minus_3_diluted_shares",
        "annual_sbc",
        "sbc_to_revenue",
        "revenue_cagr3",
        "opinc_cagr3",
        "fcf_cagr3",
        "fcf_per_share_cagr3",
    }
    if not required_cols.issubset(set(df.columns)):
        return True
    meta = manifest.get("br01_br02_enrichment", {})
    return not (
        meta.get("schema") == ENRICHMENT_SCHEMA
        and meta.get("latest_available_quarter") == latest_key
    )


def choose_annual_history(sub: pd.DataFrame, universe_ciks: set[str]) -> pd.DataFrame:
    work = sub[sub["cik"].isin(universe_ciks)].copy()
    work["form"] = work["form"].astype(str).str.upper().str.strip()
    work = work[work["form"].isin(bridge.ANNUAL_FORMS)].copy()
    work["filed_num"] = pd.to_numeric(work["filed"], errors="coerce")
    work["period_num"] = pd.to_numeric(work["period"], errors="coerce")
    work = work.sort_values(
        ["cik", "period_num", "filed_num"],
        ascending=[True, False, False],
    )

    # One filing for each fiscal year; then retain the latest four years.
    work = work.drop_duplicates(["cik", "period_num"], keep="first")
    work["history_rank"] = work.groupby("cik").cumcount()
    return work[work["history_rank"] < HISTORY_YEARS].copy()


def scan_nums(zip_infos: list[tuple[bridge.QuarterLink, Path]], adsh_set: set[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for q, path in zip_infos:
        with zipfile.ZipFile(path) as zf:
            names = {n.lower(): n for n in zf.namelist()}
            actual = names.get("num.txt")
            if not actual:
                raise bridge.BridgeError(f"num.txt non presente in {q.key}")
            with zf.open(actual) as f:
                reader = pd.read_csv(
                    f,
                    sep="\t",
                    dtype=str,
                    low_memory=False,
                    chunksize=250_000,
                )
                for chunk in reader:
                    if "adsh" not in chunk.columns or "tag" not in chunk.columns:
                        raise bridge.BridgeError(f"NUM SEC {q.key}: colonne adsh/tag assenti")
                    mask = chunk["adsh"].isin(adsh_set) & chunk["tag"].isin(RELEVANT_TAGS)
                    if "coreg" in chunk.columns:
                        mask &= chunk["coreg"].fillna("").eq("")
                    if "segments" in chunk.columns:
                        mask &= chunk["segments"].fillna("").eq("")
                    part = chunk.loc[mask].copy()
                    if len(part):
                        part["sec_source_quarter"] = q.key
                        frames.append(part)

    if not frames:
        return pd.DataFrame(
            columns=["adsh", "tag", "ddate", "qtrs", "uom", "value", "value_num", "ddate_num", "qtrs_num"]
        )

    out = pd.concat(frames, ignore_index=True, sort=False)
    out["value_num"] = pd.to_numeric(out.get("value"), errors="coerce")
    out["ddate_num"] = pd.to_numeric(out.get("ddate"), errors="coerce")
    out["qtrs_num"] = pd.to_numeric(out.get("qtrs"), errors="coerce")
    return out


def pick_flow_current(
    nums: pd.DataFrame,
    adsh: str,
    tags: list[str],
    uom: str,
) -> tuple[float | None, str, str]:
    cur, tag, ddate, _, _ = bridge._pick_tag_values(nums, adsh, tags, 4, uom)
    return cur, tag, ddate


def pick_sbc_current(nums: pd.DataFrame, adsh: str) -> tuple[float | None, str, str]:
    cur, tag, ddate, _, _ = bridge._pick_tag_values(nums, adsh, SBC_TAGS, 4, "USD")
    return cur, tag, ddate


def cagr3(current: float | None, old: float | None) -> float | None:
    if current is None or old is None:
        return None
    if not math.isfinite(float(current)) or not math.isfinite(float(old)):
        return None
    # CAGR is not economically meaningful when either endpoint is <= 0.
    if current <= 0 or old <= 0:
        return None
    return (current / old) ** (1.0 / 3.0) - 1.0


def fcf(ocf: float | None, capex: float | None) -> float | None:
    if ocf is None or capex is None:
        return None
    return ocf - abs(capex)


def per_share(value: float | None, shares: float | None) -> float | None:
    if value is None or shares is None or shares <= 0:
        return None
    return value / shares


def history_value(
    nums: pd.DataFrame,
    filing: pd.Series | None,
    metric: str,
) -> tuple[float | None, str, str]:
    if filing is None:
        return None, "", ""
    adsh = bridge.norm_text(filing.get("adsh", ""))
    if not adsh:
        return None, "", ""
    if metric in FLOW_METRICS:
        uom = "shares" if metric == "diluted_shares" else "USD"
        return pick_flow_current(nums, adsh, FLOW_METRICS[metric], uom)
    if metric in HISTORY_INSTANT_METRICS:
        return bridge._pick_instant(nums, adsh, HISTORY_INSTANT_METRICS[metric], "USD")
    raise KeyError(metric)


def enrich_dataframe(
    fundamentals: pd.DataFrame,
    history: pd.DataFrame,
    nums: pd.DataFrame,
) -> pd.DataFrame:
    out = fundamentals.copy()

    # Build a per-CIK map of the last four annual filings.
    history_map: dict[str, dict[int, pd.Series]] = {}
    for _, r in history.iterrows():
        cik = bridge.norm_text(r.get("cik", ""))
        rank = int(r["history_rank"])
        history_map.setdefault(cik, {})[rank] = r

    metrics = [
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
        "diluted_shares",
        "equity",
    ]

    records = []
    for _, base_row in out.iterrows():
        row = base_row.to_dict()
        cik = bridge.norm_text(row.get("cik", ""))
        filings = history_map.get(cik, {})

        # Explicit FY-1/FY-2/FY-3 history. Keep original annual_* fields untouched.
        for rank, prefix in [(1, "fy_minus_1"), (2, "fy_minus_2"), (3, "fy_minus_3")]:
            filing = filings.get(rank)
            row[f"{prefix}_period"] = bridge.norm_text(filing.get("period", "")) if filing is not None else ""
            row[f"{prefix}_filed"] = bridge.norm_text(filing.get("filed", "")) if filing is not None else ""
            row[f"{prefix}_adsh"] = bridge.norm_text(filing.get("adsh", "")) if filing is not None else ""

            for metric in metrics:
                val, tag, ddate = history_value(nums, filing, metric)
                row[f"{prefix}_{metric}"] = val
                row[f"{prefix}_{metric}_tag"] = tag
                row[f"{prefix}_{metric}_date"] = ddate

        # Prefer the explicit FY-1 annual filing for prior values when available.
        # This improves provenance but never invents a value.
        for metric in FLOW_METRICS:
            explicit = row.get(f"fy_minus_1_{metric}")
            if pd.notna(explicit):
                row[f"prior_{metric}"] = explicit
                row[f"prior_{metric}_date"] = row.get(f"fy_minus_1_{metric}_date", "")

        # BR-02: SBC current and prior.
        current_filing = filings.get(0)
        prior_filing = filings.get(1)

        if current_filing is not None:
            current_adsh = bridge.norm_text(current_filing.get("adsh", ""))
            sbc, sbc_tag, sbc_date = pick_sbc_current(nums, current_adsh)
        else:
            sbc, sbc_tag, sbc_date = None, "", ""

        if prior_filing is not None:
            prior_adsh = bridge.norm_text(prior_filing.get("adsh", ""))
            prior_sbc, prior_sbc_tag, prior_sbc_date = pick_sbc_current(nums, prior_adsh)
        else:
            prior_sbc, prior_sbc_tag, prior_sbc_date = None, "", ""

        row["annual_sbc"] = sbc
        row["annual_sbc_tag"] = sbc_tag
        row["annual_sbc_date"] = sbc_date
        row["prior_sbc"] = prior_sbc
        row["prior_sbc_tag"] = prior_sbc_tag
        row["prior_sbc_date"] = prior_sbc_date
        row["sbc_to_revenue"] = (
            sbc / row["annual_revenue"]
            if sbc is not None and pd.notna(row.get("annual_revenue")) and row.get("annual_revenue") not in (0, None)
            else None
        )

        # Deterministic derived growth fields used by V4.1.
        current_fcf = fcf(row.get("annual_operating_cash_flow"), row.get("annual_capex"))
        old_fcf = fcf(row.get("fy_minus_3_operating_cash_flow"), row.get("fy_minus_3_capex"))
        current_fcf_ps = per_share(current_fcf, row.get("annual_diluted_shares"))
        old_fcf_ps = per_share(old_fcf, row.get("fy_minus_3_diluted_shares"))

        row["revenue_cagr3"] = cagr3(row.get("annual_revenue"), row.get("fy_minus_3_revenue"))
        row["opinc_cagr3"] = cagr3(row.get("annual_operating_income"), row.get("fy_minus_3_operating_income"))
        row["fcf_cagr3"] = cagr3(current_fcf, old_fcf)
        row["fcf_per_share_cagr3"] = cagr3(current_fcf_ps, old_fcf_ps)

        # Raw four-year operating margins for downstream stability logic.
        margins = []
        for pfx in ["annual", "fy_minus_1", "fy_minus_2", "fy_minus_3"]:
            op = row.get(f"{pfx}_operating_income")
            rev = row.get(f"{pfx}_revenue")
            margin = op / rev if op is not None and rev not in (None, 0) and pd.notna(op) and pd.notna(rev) else None
            row[f"{pfx}_operating_margin_history"] = margin
            if margin is not None and math.isfinite(float(margin)):
                margins.append(float(margin))

        if len(margins) >= 3:
            row["operating_margin_std_4y"] = float(pd.Series(margins).std(ddof=0))
            row["operating_margin_range_4y"] = max(margins) - min(margins)
        else:
            row["operating_margin_std_4y"] = None
            row["operating_margin_range_4y"] = None

        records.append(row)

    return pd.DataFrame(records)


def pct_present(series: pd.Series) -> float:
    return round(float(series.notna().mean() * 100), 1) if len(series) else 0.0


def update_coverage_file(df: pd.DataFrame) -> None:
    if COVERAGE_PATH.exists():
        cov = pd.read_csv(COVERAGE_PATH, low_memory=False)
    else:
        cov = df[["ticker", "name", "cik"]].copy()

    key = "ticker"
    extra = pd.DataFrame({
        key: df[key],
        "history_revenue_4y": df["fy_minus_3_revenue"].notna(),
        "history_opinc_4y": df["fy_minus_3_operating_income"].notna(),
        "history_fcf_4y": (
            df["fy_minus_3_operating_cash_flow"].notna()
            & df["fy_minus_3_capex"].notna()
        ),
        "history_diluted_shares_4y": df["fy_minus_3_diluted_shares"].notna(),
        "sbc_current_present": df["annual_sbc"].notna(),
        "revenue_cagr3_present": df["revenue_cagr3"].notna(),
        "opinc_cagr3_present": df["opinc_cagr3"].notna(),
        "fcf_cagr3_present": df["fcf_cagr3"].notna(),
        "fcf_per_share_cagr3_present": df["fcf_per_share_cagr3"].notna(),
    })

    for c in extra.columns:
        if c != key and c in cov.columns:
            cov = cov.drop(columns=[c])

    cov = cov.merge(extra, on=key, how="left")
    bridge.write_csv_atomic(COVERAGE_PATH, cov)


def update_status(df: pd.DataFrame, quarters: list[str]) -> dict:
    stats = {
        "revenue_4y_pct": pct_present(df["fy_minus_3_revenue"]),
        "operating_income_4y_pct": pct_present(df["fy_minus_3_operating_income"]),
        "fcf_4y_pct": round(float((
            df["fy_minus_3_operating_cash_flow"].notna()
            & df["fy_minus_3_capex"].notna()
        ).mean() * 100), 1),
        "diluted_shares_4y_pct": pct_present(df["fy_minus_3_diluted_shares"]),
        "sbc_current_pct": pct_present(df["annual_sbc"]),
        "revenue_cagr3_pct": pct_present(df["revenue_cagr3"]),
        "opinc_cagr3_pct": pct_present(df["opinc_cagr3"]),
        "fcf_cagr3_pct": pct_present(df["fcf_cagr3"]),
        "fcf_per_share_cagr3_pct": pct_present(df["fcf_per_share_cagr3"]),
    }

    marker = "\n## V4.1 enrichment BR-01 / BR-02\n"
    base = STATUS_PATH.read_text(encoding="utf-8") if STATUS_PATH.exists() else "# Investment OS Data Bridge — stato\n"
    if marker in base:
        base = base.split(marker, 1)[0].rstrip() + "\n"

    section = f"""
## V4.1 enrichment BR-01 / BR-02

- SEC quarterly datasets usati per lo storico: **{len(quarters)}** ({quarters[0]} → {quarters[-1]})
- Storico ricavi a 4 esercizi: **{stats['revenue_4y_pct']:.1f}%**
- Storico operating income a 4 esercizi: **{stats['operating_income_4y_pct']:.1f}%**
- Storico FCF a 4 esercizi: **{stats['fcf_4y_pct']:.1f}%**
- Storico diluted shares a 4 esercizi: **{stats['diluted_shares_4y_pct']:.1f}%**
- SBC corrente disponibile: **{stats['sbc_current_pct']:.1f}%**
- Revenue CAGR 3y calcolabile: **{stats['revenue_cagr3_pct']:.1f}%**
- Operating-income CAGR 3y calcolabile: **{stats['opinc_cagr3_pct']:.1f}%**
- FCF CAGR 3y calcolabile: **{stats['fcf_cagr3_pct']:.1f}%**
- FCF/share CAGR 3y calcolabile: **{stats['fcf_per_share_cagr3_pct']:.1f}%**

`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
"""
    STATUS_PATH.write_text(base.rstrip() + "\n" + section.lstrip(), encoding="utf-8")
    return stats


def main() -> int:
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato: eseguire prima src/bridge.py")

    fundamentals = pd.read_csv(FUNDAMENTALS_PATH, low_memory=False)
    manifest = read_manifest()
    downloader = bridge.Downloader()

    quarters, sec_index_meta = bridge.discover_sec_quarters(downloader)
    selected_quarters = quarters[-SEC_QUARTERS:]
    latest_key = quarters[-1].key

    if not needs_enrichment(fundamentals, manifest, latest_key):
        print(
            f"BR-01/BR-02 già applicati per {latest_key}; "
            "nessun download SEC storico necessario."
        )
        return 0

    print(
        f"BR-01/BR-02: scarico {len(selected_quarters)} SEC datasets "
        f"({selected_quarters[0].key} → {selected_quarters[-1].key})..."
    )

    with tempfile.TemporaryDirectory(prefix="investment_os_br01_br02_") as td:
        td_path = Path(td)
        zip_infos: list[tuple[bridge.QuarterLink, Path]] = []
        downloads = []

        for q in selected_quarters:
            path = td_path / f"{q.key}.zip"
            print(f"  Scarico {q.label} ...")
            sha, nbytes = bridge.download_to_file(downloader, q.url, path)
            zip_infos.append((q, path))
            downloads.append({
                "quarter": q.key,
                "url": q.url,
                "sha256": sha,
                "bytes": nbytes,
            })

        subs = bridge.load_submissions_from_zips(zip_infos)
        universe_ciks = set(
            fundamentals["cik"]
            .dropna()
            .astype(str)
            .map(lambda x: x.zfill(10))
        )

        history = choose_annual_history(subs, universe_ciks)
        adsh_set = set(history["adsh"].dropna().astype(str))
        print(
            f"  Filing annuali storici selezionati: {len(history)}; "
            "scansione NUM per BR-01/BR-02..."
        )

        nums = scan_nums(zip_infos, adsh_set)
        enriched = enrich_dataframe(fundamentals, history, nums)

    bridge.write_csv_atomic(FUNDAMENTALS_PATH, enriched)
    update_coverage_file(enriched)
    stats = update_status(enriched, [q.key for q in selected_quarters])

    manifest = read_manifest()
    manifest["schema_version"] = "1.1"
    manifest["br01_br02_enrichment"] = {
        "schema": ENRICHMENT_SCHEMA,
        "updated_at_utc": now_iso(),
        "latest_available_quarter": latest_key,
        "quarters_used": [q.key for q in selected_quarters],
        "annual_history_years_target": HISTORY_YEARS,
        "sec_index": sec_index_meta,
        "quarter_downloads": downloads,
        "coverage": stats,
        "rules": [
            "Missing values are never converted to zero.",
            "3-year CAGR is calculated only when both endpoints are positive.",
            "SBC prefers ShareBasedCompensation; missing SBC remains MISSING.",
            "This enrichment does not compute BQS, IOS, rankings, or recommendations.",
        ],
    }

    outputs = manifest.setdefault("outputs", {})
    for name in [
        "sp500_fundamentals.csv",
        "sp500_coverage.csv",
        "status.md",
    ]:
        path = DATA_DIR / name
        if path.exists():
            outputs[name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }

    write_manifest(manifest)

    print("OK — BR-01 + BR-02 completati.")
    for k, v in stats.items():
        print(f"{k}: {v:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
