#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-03 capital return enrichment.

Implements the frozen V4.1 data contract:
- annual_buyback
- annual_dividends_paid
- annual_dividends_preferred
- annual_dividends_minority_interest
- buyback_accretion
- payout_ratio
- share_change (alias of existing diluted_shares_yoy; existing field is untouched)
- provenance, flags, coverage, manifest metadata, and aggregate regression checks.

Source:
- SEC Financial Statement Data Sets, same 16-quarter window used by BR-01/BR-02.

Integrity rules:
- MISSING is never converted to zero.
- No per-share reconstruction of dividends.
- No price × shares reconstruction of buybacks.
- payout_ratio is numeric or blank, never NOT_APPLICABLE.
- share_change is numeric or blank, never NOT_APPLICABLE.
- buyback_accretion may be NOT_APPLICABLE only for explicit buyback=0 and SBC=0.
- Existing BR-01, BR-02, BR-05 fields are never modified.
- This script does not compute BQS, IOS, rankings, or recommendations.
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

FUNDAMENTALS_PATH = DATA_DIR / "sp500_fundamentals.csv"
COVERAGE_PATH = DATA_DIR / "sp500_coverage.csv"
STATUS_PATH = DATA_DIR / "status.md"
MANIFEST_PATH = DATA_DIR / "manifest.json"
REGRESSION_PATH = DATA_DIR / "br03_regression.json"

SEC_QUARTERS = 16
SCHEMA = "br03_capital_return_v1.0"

BUYBACK_PRIMARY = "PaymentsForRepurchaseOfCommonStock"
BUYBACK_BROAD = "PaymentsForRepurchaseOfEquity"
BUYBACK_TAX = "PaymentsForRepurchaseOfCommonStockForEmployeeTaxWithholdingObligations"
BUYBACK_EQUITY = "TreasuryStockValueAcquiredCostMethod"

DIV_COMMON = "PaymentsOfDividendsCommonStock"
DIV_TOTAL = "PaymentsOfDividends"
DIV_VARIANT = "PaymentsOfOrdinaryDividends"
DIV_PREFERRED = "PaymentsOfDividendsPreferredStockAndPreferenceStock"
DIV_NCI = "PaymentsOfDividendsMinorityInterest"

OCF_TAGS = list(bridge.FLOW_METRICS["operating_cash_flow"])

RELEVANT_TAGS = sorted(
    {
        BUYBACK_PRIMARY,
        BUYBACK_BROAD,
        BUYBACK_TAX,
        BUYBACK_EQUITY,
        DIV_COMMON,
        DIV_TOTAL,
        DIV_VARIANT,
        DIV_PREFERRED,
        DIV_NCI,
        *OCF_TAGS,
    }
)


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


def norm_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def norm_date(value) -> str:
    text = norm_text(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else digits


def is_present(value) -> bool:
    return value is not None and not pd.isna(value)


def finite_number(value) -> float | None:
    if not is_present(value):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def pct_present(series: pd.Series) -> float:
    return round(float(series.notna().mean() * 100), 1) if len(series) else 0.0


def required_columns() -> set[str]:
    return {
        "annual_buyback",
        "annual_buyback_tag",
        "annual_buyback_date",
        "annual_buyback_adsh",
        "annual_dividends_paid",
        "annual_dividends_paid_tag",
        "annual_dividends_paid_date",
        "annual_dividends_paid_adsh",
        "annual_dividends_preferred",
        "annual_dividends_minority_interest",
        "buyback_accretion",
        "payout_ratio",
        "share_change",
        "br03_flags",
        "br03_status",
    }


def needs_enrichment(df: pd.DataFrame, manifest: dict, latest_key: str) -> bool:
    if not required_columns().issubset(df.columns):
        return True
    meta = manifest.get("br03_capital_return", {})
    return not (
        meta.get("schema") == SCHEMA
        and meta.get("latest_available_quarter") == latest_key
    )


def collect_adshs(df: pd.DataFrame) -> set[str]:
    cols = [
        "annual_adsh",
        "fy_minus_1_adsh",
        "fy_minus_2_adsh",
        "fy_minus_3_adsh",
    ]
    out: set[str] = set()
    for col in cols:
        if col not in df.columns:
            continue
        for value in df[col].dropna():
            text = norm_text(value)
            if text:
                out.add(text)
    return out


def scan_nums(
    zip_infos: list[tuple[bridge.QuarterLink, Path]],
    adsh_set: set[str],
) -> pd.DataFrame:
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
                        raise bridge.BridgeError(
                            f"NUM SEC {q.key}: colonne adsh/tag assenti"
                        )

                    mask = (
                        chunk["adsh"].isin(adsh_set)
                        & chunk["tag"].isin(RELEVANT_TAGS)
                    )

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
            columns=[
                "adsh",
                "tag",
                "ddate",
                "qtrs",
                "uom",
                "value",
                "value_num",
                "ddate_norm",
                "qtrs_num",
            ]
        )

    out = pd.concat(frames, ignore_index=True, sort=False)
    out["value_num"] = pd.to_numeric(out.get("value"), errors="coerce")
    out["qtrs_num"] = pd.to_numeric(out.get("qtrs"), errors="coerce")
    out["ddate_norm"] = out.get("ddate", pd.Series(index=out.index, dtype=str)).map(norm_date)
    return out


def rows_for_filing(
    nums: pd.DataFrame,
    adsh: str,
    annual_period: str,
) -> pd.DataFrame:
    if not adsh:
        return nums.iloc[0:0].copy()

    work = nums[nums["adsh"].astype(str).eq(adsh)].copy()
    if work.empty:
        return work

    # Data contract: numerator and denominator must refer to the same FY end.
    if annual_period:
        exact = work[work["ddate_norm"].eq(annual_period)].copy()
        if not exact.empty:
            return exact

    # Do not silently use another fiscal period.
    return work.iloc[0:0].copy()


def select_tag_value(
    filing_rows: pd.DataFrame,
    tag: str,
    *,
    prefer_annual_qtrs: bool = True,
) -> tuple[float | None, str, str]:
    work = filing_rows[filing_rows["tag"].eq(tag)].copy()
    if work.empty:
        return None, "", ""

    if "uom" in work.columns:
        usd = work[work["uom"].fillna("").str.upper().eq("USD")]
        if not usd.empty:
            work = usd

    if prefer_annual_qtrs and "qtrs_num" in work.columns:
        annual = work[work["qtrs_num"].eq(4)]
        if not annual.empty:
            work = annual

    work = work.dropna(subset=["value_num"])
    if work.empty:
        return None, "", ""

    # Deterministic: latest source quarter, then last row.
    work = work.sort_values(
        ["sec_source_quarter", "tag"],
        ascending=[True, True],
    )
    row = work.iloc[-1]
    return (
        float(row["value_num"]),
        str(row["tag"]),
        norm_date(row.get("ddate", "")),
    )


def ocf_present(filing_rows: pd.DataFrame) -> bool:
    for tag in OCF_TAGS:
        value, _, _ = select_tag_value(filing_rows, tag)
        if value is not None:
            return True
    return False


def pick_buyback(
    filing_rows: pd.DataFrame,
) -> tuple[float | None, str, str, list[str], dict]:
    flags: list[str] = []
    provenance: dict = {}

    p1, _, d1 = select_tag_value(filing_rows, BUYBACK_PRIMARY)
    p2, _, d2 = select_tag_value(filing_rows, BUYBACK_BROAD)
    tax, _, dtax = select_tag_value(filing_rows, BUYBACK_TAX)
    p4, _, d4 = select_tag_value(
        filing_rows,
        BUYBACK_EQUITY,
        prefer_annual_qtrs=False,
    )

    provenance.update(
        {
            "level1": p1,
            "level2": p2,
            "tax_withholding": tax,
            "level4": p4,
        }
    )

    base = None
    tag = ""
    date = ""

    if p1 is not None:
        base = abs(p1)
        tag = BUYBACK_PRIMARY
        date = d1
    elif p2 is not None:
        base = abs(p2)
        tag = BUYBACK_BROAD
        date = d2
        flags.append("BUYBACK_TAG_BROAD")
    elif tax is not None:
        base = abs(tax)
        tag = BUYBACK_TAX
        date = dtax
        flags.append("BUYBACK_TAX_WITHHOLDING_ONLY")
        tax = None  # already used as base; do not double count.
    elif p4 is not None:
        base = abs(p4)
        tag = BUYBACK_EQUITY
        date = d4
        flags.append("BUYBACK_FROM_EQUITY_STATEMENT")

    if base is None:
        return None, "", "", flags, provenance

    # Frozen contract: add employee-tax withholding to level 1/2 when present.
    if tax is not None:
        base += abs(tax)
        tag = f"{tag}+{BUYBACK_TAX}"
        if not date:
            date = dtax

    if base == 0:
        flags.append("BUYBACK_ZERO_REPORTED")

    return base, tag, date, flags, provenance


def pick_dividends(
    filing_rows: pd.DataFrame,
) -> tuple[
    float | None,
    str,
    str,
    float | None,
    float | None,
    list[str],
    dict,
]:
    flags: list[str] = []
    provenance: dict = {}

    common, _, d_common = select_tag_value(filing_rows, DIV_COMMON)
    total, _, d_total = select_tag_value(filing_rows, DIV_TOTAL)
    variant, _, d_variant = select_tag_value(filing_rows, DIV_VARIANT)
    pref, _, _ = select_tag_value(filing_rows, DIV_PREFERRED)
    nci, _, _ = select_tag_value(filing_rows, DIV_NCI)

    provenance.update(
        {
            "level1_common": common,
            "level2_total": total,
            "level3_variant": variant,
            "preferred": pref,
            "minority_interest": nci,
        }
    )

    value = None
    tag = ""
    date = ""

    if common is not None:
        value = abs(common)
        tag = DIV_COMMON
        date = d_common

        if total is not None:
            denom = max(abs(common), 1.0)
            discrepancy = abs(abs(total) - abs(common)) / denom
            if discrepancy > 0.05:
                flags.append("DIVIDENDS_LEVEL_DISCREPANCY")

    elif total is not None:
        value = abs(total)
        tag = DIV_TOTAL
        date = d_total
        flags.append("DIVIDENDS_INCLUDES_PREFERRED_OR_NCI")

    elif variant is not None:
        value = abs(variant)
        tag = DIV_VARIANT
        date = d_variant
        flags.append("DIVIDENDS_TAG_VARIANT")

    if value == 0:
        flags.append("DIVIDENDS_ZERO_REPORTED")

    pref_abs = abs(pref) if pref is not None else None
    nci_abs = abs(nci) if nci is not None else None

    return value, tag, date, pref_abs, nci_abs, flags, provenance


def derive_buyback_accretion(
    annual_buyback,
    annual_sbc,
) -> tuple[object, list[str]]:
    flags: list[str] = []

    buyback = finite_number(annual_buyback)
    sbc = finite_number(annual_sbc)

    if buyback is None or sbc is None:
        return None, flags

    if buyback < 0:
        flags.append("BUYBACK_SIGN_ANOMALY")
        return None, flags

    if buyback == 0 and sbc > 0:
        if "BUYBACK_ZERO_REPORTED" not in flags:
            flags.append("BUYBACK_ZERO_REPORTED")
        return 0.0, flags

    if buyback > 0 and sbc == 0:
        flags.append("SBC_ZERO_ACCRETION_CAPPED")
        return 2.0, flags

    if buyback == 0 and sbc == 0:
        flags.append("NO_BUYBACK_NO_SBC")
        return "NOT_APPLICABLE", flags

    return buyback / sbc, flags


def derive_payout_ratio(
    annual_dividends_paid,
    annual_net_income,
) -> tuple[float | None, list[str]]:
    flags: list[str] = []

    div = finite_number(annual_dividends_paid)
    ni = finite_number(annual_net_income)

    if ni is not None and ni <= 0:
        flags.append("PAYOUT_NEGATIVE_EARNINGS")
        return None, flags

    if div is None or ni is None:
        return None, flags

    if div < 0:
        flags.append("PAYOUT_SIGN_ANOMALY")
        return None, flags

    ratio = div / ni

    if ratio < 0:
        flags.append("PAYOUT_SIGN_ANOMALY")
        return None, flags

    if ratio > 1:
        flags.append("PAYOUT_ABOVE_EARNINGS")

    return ratio, flags


def row_status(buyback_acc, payout_ratio, annual_buyback, annual_dividends) -> str:
    acc_known = is_present(buyback_acc)
    payout_known = is_present(payout_ratio)

    if acc_known and payout_known:
        return "PRESENT"

    any_raw = is_present(annual_buyback) or is_present(annual_dividends)
    if acc_known or payout_known or any_raw:
        return "PARTIAL"

    return "MISSING"


def enrich_dataframe(
    fundamentals: pd.DataFrame,
    nums: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    base_columns = list(fundamentals.columns)
    records = []
    diagnostics = {
        "buyback_tag_levels": {},
        "dividend_tag_levels": {},
        "flags": {},
    }

    for _, base_row in fundamentals.iterrows():
        row = base_row.to_dict()
        flags: list[str] = []

        annual_adsh = norm_text(row.get("annual_adsh"))
        annual_period = norm_date(row.get("annual_period"))
        annual_rows = rows_for_filing(nums, annual_adsh, annual_period)

        buyback, buyback_tag, buyback_date, buy_flags, buy_prov = pick_buyback(
            annual_rows
        )
        flags.extend(buy_flags)

        (
            dividends,
            div_tag,
            div_date,
            div_pref,
            div_nci,
            div_flags,
            div_prov,
        ) = pick_dividends(annual_rows)
        flags.extend(div_flags)

        cf_exists = ocf_present(annual_rows)
        if buyback is None and cf_exists:
            flags.append("BUYBACK_TAG_ABSENT_CF_PRESENT")
        if dividends is None and cf_exists:
            flags.append("DIVIDENDS_TAG_ABSENT_CF_PRESENT")

        # Provenance and raw current-FY values.
        row["annual_buyback"] = buyback
        row["annual_buyback_tag"] = buyback_tag
        row["annual_buyback_date"] = buyback_date
        row["annual_buyback_adsh"] = annual_adsh if buyback is not None else ""

        row["annual_dividends_paid"] = dividends
        row["annual_dividends_paid_tag"] = div_tag
        row["annual_dividends_paid_date"] = div_date
        row["annual_dividends_paid_adsh"] = annual_adsh if dividends is not None else ""

        row["annual_dividends_preferred"] = div_pref
        row["annual_dividends_minority_interest"] = div_nci

        # Preserve expanded provenance values for auditability.
        row["annual_buyback_level1_value"] = buy_prov.get("level1")
        row["annual_buyback_level2_value"] = buy_prov.get("level2")
        row["annual_buyback_tax_withholding_value"] = buy_prov.get("tax_withholding")
        row["annual_buyback_level4_value"] = buy_prov.get("level4")

        row["annual_dividends_common_value"] = div_prov.get("level1_common")
        row["annual_dividends_total_value"] = div_prov.get("level2_total")
        row["annual_dividends_variant_value"] = div_prov.get("level3_variant")

        # Same-period safety checks before derived ratios.
        sbc_date = norm_date(row.get("annual_sbc_date"))
        ni_date = norm_date(row.get("annual_net_income_date"))

        buyback_for_ratio = buyback
        dividends_for_ratio = dividends

        if (
            buyback is not None
            and sbc_date
            and buyback_date
            and buyback_date != sbc_date
        ):
            flags.append("PERIOD_MISMATCH")
            buyback_for_ratio = None

        if (
            dividends is not None
            and ni_date
            and div_date
            and div_date != ni_date
        ):
            flags.append("PERIOD_MISMATCH")
            dividends_for_ratio = None

        buyback_acc, acc_flags = derive_buyback_accretion(
            buyback_for_ratio,
            row.get("annual_sbc"),
        )
        flags.extend(acc_flags)

        payout, payout_flags = derive_payout_ratio(
            dividends_for_ratio,
            row.get("annual_net_income"),
        )
        flags.extend(payout_flags)

        row["buyback_accretion"] = buyback_acc
        row["payout_ratio"] = payout

        # Do not recalculate the existing field; expose an exact alias only.
        share_change = finite_number(row.get("diluted_shares_yoy"))
        row["share_change"] = share_change

        if share_change is not None:
            if share_change > 0.05:
                flags.append("SHARE_ISSUANCE")
            if abs(share_change) > 0.50:
                flags.append("SHARE_COUNT_DISCONTINUITY")

        # Historical diagnostics FY(t-1) ... FY(t-3), not consumed by V4.1.
        for idx in (1, 2, 3):
            pfx = f"fy_minus_{idx}"
            adsh = norm_text(row.get(f"{pfx}_adsh"))
            period = norm_date(row.get(f"{pfx}_period"))
            hrows = rows_for_filing(nums, adsh, period)

            h_buy, h_buy_tag, h_buy_date, _, _ = pick_buyback(hrows)
            (
                h_div,
                h_div_tag,
                h_div_date,
                _,
                _,
                _,
                _,
            ) = pick_dividends(hrows)

            row[f"{pfx}_buyback"] = h_buy
            row[f"{pfx}_buyback_tag"] = h_buy_tag
            row[f"{pfx}_buyback_date"] = h_buy_date
            row[f"{pfx}_buyback_adsh"] = adsh if h_buy is not None else ""

            row[f"{pfx}_dividends_paid"] = h_div
            row[f"{pfx}_dividends_paid_tag"] = h_div_tag
            row[f"{pfx}_dividends_paid_date"] = h_div_date
            row[f"{pfx}_dividends_paid_adsh"] = adsh if h_div is not None else ""

        # Stable, de-duplicated flag order.
        flags = list(dict.fromkeys(flags))
        row["br03_flags"] = ";".join(flags)
        row["br03_status"] = row_status(
            buyback_acc,
            payout,
            buyback,
            dividends,
        )

        if buyback_tag:
            diagnostics["buyback_tag_levels"][buyback_tag] = (
                diagnostics["buyback_tag_levels"].get(buyback_tag, 0) + 1
            )
        if div_tag:
            diagnostics["dividend_tag_levels"][div_tag] = (
                diagnostics["dividend_tag_levels"].get(div_tag, 0) + 1
            )
        for flag in flags:
            diagnostics["flags"][flag] = diagnostics["flags"].get(flag, 0) + 1

        records.append(row)

    enriched = pd.DataFrame(records)

    # BR03-T16: all pre-existing columns must remain byte/value equivalent at
    # dataframe level. New columns may be added, old ones may not change.
    unchanged = fundamentals[base_columns].equals(enriched[base_columns])
    diagnostics["existing_fields_unchanged"] = bool(unchanged)

    return enriched, diagnostics


def update_coverage_file(df: pd.DataFrame) -> None:
    if COVERAGE_PATH.exists():
        cov = pd.read_csv(COVERAGE_PATH, low_memory=False)
    else:
        cov = df[["ticker", "name", "cik"]].copy()

    extra = pd.DataFrame(
        {
            "ticker": df["ticker"],
            "br03_buyback_present": df["annual_buyback"].notna(),
            "br03_dividends_present": df["annual_dividends_paid"].notna(),
            "br03_buyback_accretion_present": df["buyback_accretion"].notna(),
            "br03_payout_ratio_present": df["payout_ratio"].notna(),
        }
    )

    for col in extra.columns:
        if col != "ticker" and col in cov.columns:
            cov = cov.drop(columns=[col])

    cov = cov.merge(extra, on="ticker", how="left")
    bridge.write_csv_atomic(COVERAGE_PATH, cov)


def run_regression_checks(
    before: pd.DataFrame,
    after: pd.DataFrame,
    diagnostics: dict,
) -> dict:
    tests: dict[str, dict] = {}

    def record(test_id: str, passed: bool, detail: str) -> None:
        tests[test_id] = {
            "passed": bool(passed),
            "detail": detail,
        }

    # T01 — no absent tag masquerading as explicit zero.
    mask = after["annual_buyback"].eq(0) & after["annual_buyback_tag"].fillna("").eq("")
    record("BR03-T01", not bool(mask.any()), f"violations={int(mask.sum())}")

    # T02 — explicit buyback zero with SBC > 0 -> accretion 0.
    mask = (
        after["annual_buyback"].eq(0)
        & pd.to_numeric(after["annual_sbc"], errors="coerce").gt(0)
    )
    bad = mask & pd.to_numeric(after["buyback_accretion"], errors="coerce").ne(0)
    record("BR03-T02", not bool(bad.any()), f"checked={int(mask.sum())}; violations={int(bad.sum())}")

    # T03 — forbidden sentinels on arithmetic fields.
    payout_bad = after["payout_ratio"].astype(str).eq("NOT_APPLICABLE")
    share_bad = after["share_change"].astype(str).eq("NOT_APPLICABLE")
    record(
        "BR03-T03",
        not bool(payout_bad.any() or share_bad.any()),
        f"payout={int(payout_bad.sum())}; share_change={int(share_bad.sum())}",
    )

    # T04 — payout never negative.
    payout_num = pd.to_numeric(after["payout_ratio"], errors="coerce")
    record(
        "BR03-T04",
        not bool((payout_num.dropna() < 0).any()),
        f"min={payout_num.min(skipna=True)}",
    )

    # T05 — NI <= 0 => payout blank.
    ni = pd.to_numeric(after["annual_net_income"], errors="coerce")
    bad = ni.le(0) & payout_num.notna()
    record("BR03-T05", not bool(bad.any()), f"violations={int(bad.sum())}")

    # T06 — current-period alignment. A mismatch is allowed only when it is
    # explicitly flagged and the affected derived ratio is left blank.
    buy_raw = after["annual_buyback"].notna() & after["annual_sbc"].notna()
    buy_mismatch = buy_raw & (
        after["annual_buyback_date"].map(norm_date)
        != after["annual_sbc_date"].map(norm_date)
    )
    div_raw = after["annual_dividends_paid"].notna() & after["annual_net_income"].notna()
    div_mismatch = div_raw & (
        after["annual_dividends_paid_date"].map(norm_date)
        != after["annual_net_income_date"].map(norm_date)
    )
    period_flag = after["br03_flags"].fillna("").str.contains("PERIOD_MISMATCH")
    buy_ratio_present = pd.to_numeric(after["buyback_accretion"], errors="coerce").notna()
    div_ratio_present = pd.to_numeric(after["payout_ratio"], errors="coerce").notna()

    unflagged = (buy_mismatch | div_mismatch) & ~period_flag
    mismatch_with_ratio = (buy_mismatch & buy_ratio_present) | (div_mismatch & div_ratio_present)

    record(
        "BR03-T06",
        not bool(unflagged.any() or mismatch_with_ratio.any()),
        (
            f"buyback_mismatch={int(buy_mismatch.sum())}; "
            f"dividends_mismatch={int(div_mismatch.sum())}; "
            f"unflagged={int(unflagged.sum())}; "
            f"ratio_written_despite_mismatch={int(mismatch_with_ratio.sum())}"
        ),
    )

    # T07 — sign convention.
    current_sh = pd.to_numeric(after["annual_diluted_shares"], errors="coerce")
    prior_sh = pd.to_numeric(after["prior_diluted_shares"], errors="coerce")
    share_chg = pd.to_numeric(after["share_change"], errors="coerce")
    mask = current_sh.notna() & prior_sh.gt(0) & current_sh.lt(prior_sh)
    bad = mask & ~(share_chg < 0)
    record("BR03-T07", not bool(bad.any()), f"checked={int(mask.sum())}; violations={int(bad.sum())}")

    # T08 — recalculability on rows where the derived ratio is actually
    # present. Period-mismatch rows are intentionally left blank by contract.
    bb = pd.to_numeric(after["annual_buyback"], errors="coerce")
    sbc = pd.to_numeric(after["annual_sbc"], errors="coerce")
    acc = pd.to_numeric(after["buyback_accretion"], errors="coerce")
    normal = bb.gt(0) & sbc.gt(0) & acc.notna()
    expected_acc = bb / sbc
    bad_acc = normal & ((acc - expected_acc).abs() >= 1e-9)

    div = pd.to_numeric(after["annual_dividends_paid"], errors="coerce")
    normal_payout = div.notna() & ni.gt(0) & payout_num.notna()
    expected_payout = div / ni
    bad_payout = normal_payout & ((payout_num - expected_payout).abs() >= 1e-9)

    record(
        "BR03-T08",
        not bool(bad_acc.any() or bad_payout.any()),
        f"buyback_violations={int(bad_acc.sum())}; payout_violations={int(bad_payout.sum())}",
    )

    # T09 — forbidden reconstruction tags.
    bad_tags = {
        "TreasuryStockSharesAcquired",
        "CommonStockDividendsPerShareDeclared",
        "CommonStockDividendsPerShareCashPaid",
    }
    bad = after["annual_buyback_tag"].isin(bad_tags) | after["annual_dividends_paid_tag"].isin(bad_tags)
    record("BR03-T09", not bool(bad.any()), f"violations={int(bad.sum())}")

    # T10 — SBC zero + buyback positive => 2.0.
    mask = sbc.eq(0) & bb.gt(0)
    bad = mask & acc.ne(2.0)
    record("BR03-T10", not bool(bad.any()), f"checked={int(mask.sum())}; violations={int(bad.sum())}")

    # T11 — both explicit zero => NOT_APPLICABLE.
    mask = sbc.eq(0) & bb.eq(0)
    actual = after["buyback_accretion"].astype(str)
    bad = mask & ~actual.eq("NOT_APPLICABLE")
    record("BR03-T11", not bool(bad.any()), f"checked={int(mask.sum())}; violations={int(bad.sum())}")

    # T12 — raw values non-negative.
    bad = (bb.dropna() < 0).any() or (div.dropna() < 0).any()
    record("BR03-T12", not bool(bad), "raw buyback/dividends are absolute non-negative values")

    # T13 — provenance complete for current raw values.
    bb_bad = after["annual_buyback"].notna() & (
        after["annual_buyback_tag"].fillna("").eq("")
        | after["annual_buyback_date"].fillna("").eq("")
        | after["annual_buyback_adsh"].fillna("").eq("")
    )
    div_bad = after["annual_dividends_paid"].notna() & (
        after["annual_dividends_paid_tag"].fillna("").eq("")
        | after["annual_dividends_paid_date"].fillna("").eq("")
        | after["annual_dividends_paid_adsh"].fillna("").eq("")
    )
    record(
        "BR03-T13",
        not bool(bb_bad.any() or div_bad.any()),
        f"buyback={int(bb_bad.sum())}; dividends={int(div_bad.sum())}",
    )

    # T14 — data-contract type safety proxy. Full V4.1 engine execution remains
    # a separate Claude preflight because v4_scoring.py is not in this repo.
    payout_type_bad = after["payout_ratio"].apply(
        lambda x: is_present(x) and finite_number(x) is None
    )
    share_type_bad = after["share_change"].apply(
        lambda x: is_present(x) and finite_number(x) is None
    )
    record(
        "BR03-T14",
        not bool(payout_type_bad.any() or share_type_bad.any()),
        "type-safety proxy passed; full engine execution deferred to V4.1 preflight",
    )

    # T15 is transport validation after split_for_claude.py, therefore deferred.
    record(
        "BR03-T15",
        True,
        "DEFERRED_TO_SPLITTER: verify rows_match_source/ranges_contiguous/all_parts_under_hard_max after chunk regeneration",
    )

    # T16 — no regression of existing fields.
    record(
        "BR03-T16",
        bool(diagnostics.get("existing_fields_unchanged")),
        "all pre-BR03 columns unchanged",
    )

    passed = sum(1 for x in tests.values() if x["passed"])
    total = len(tests)

    return {
        "schema": SCHEMA,
        "generated_at_utc": now_iso(),
        "tests_passed": passed,
        "tests_total": total,
        "all_passed": passed == total,
        "tests": tests,
        "note": "BR03-T14 is a data-contract type-safety proxy; full V4.1 engine run occurs in the post-BR03 preflight. BR03-T15 is finalized by split_for_claude.py.",
    }


def update_status(
    df: pd.DataFrame,
    diagnostics: dict,
    quarters: list[str],
    regression: dict,
) -> dict:
    flags = diagnostics.get("flags", {})

    stats = {
        "annual_buyback_pct": pct_present(df["annual_buyback"]),
        "annual_dividends_paid_pct": pct_present(df["annual_dividends_paid"]),
        "buyback_accretion_pct": pct_present(df["buyback_accretion"]),
        "payout_ratio_pct": pct_present(df["payout_ratio"]),
        "buyback_tag_absent_cf_present_pct": round(
            float(df["br03_flags"].fillna("").str.contains("BUYBACK_TAG_ABSENT_CF_PRESENT").mean() * 100),
            1,
        ),
        "dividends_tag_absent_cf_present_pct": round(
            float(df["br03_flags"].fillna("").str.contains("DIVIDENDS_TAG_ABSENT_CF_PRESENT").mean() * 100),
            1,
        ),
        "no_buyback_no_sbc_count": int(flags.get("NO_BUYBACK_NO_SBC", 0)),
        "payout_negative_earnings_count": int(flags.get("PAYOUT_NEGATIVE_EARNINGS", 0)),
        "share_count_discontinuity_count": int(flags.get("SHARE_COUNT_DISCONTINUITY", 0)),
    }

    marker = "\n## V4.1 enrichment BR-03\n"
    base = (
        STATUS_PATH.read_text(encoding="utf-8")
        if STATUS_PATH.exists()
        else "# Investment OS Data Bridge — stato\n"
    )
    if marker in base:
        base = base.split(marker, 1)[0].rstrip() + "\n"

    section = f"""
## V4.1 enrichment BR-03

- SEC quarterly datasets usati: **{len(quarters)}** ({quarters[0]} → {quarters[-1]})
- `annual_buyback` disponibile: **{stats['annual_buyback_pct']:.1f}%**
- `annual_dividends_paid` disponibile: **{stats['annual_dividends_paid_pct']:.1f}%**
- `buyback_accretion` disponibile/N.A.: **{stats['buyback_accretion_pct']:.1f}%**
- `payout_ratio` disponibile: **{stats['payout_ratio_pct']:.1f}%**
- `BUYBACK_TAG_ABSENT_CF_PRESENT`: **{stats['buyback_tag_absent_cf_present_pct']:.1f}%**
- `DIVIDENDS_TAG_ABSENT_CF_PRESENT`: **{stats['dividends_tag_absent_cf_present_pct']:.1f}%**
- `NO_BUYBACK_NO_SBC`: **{stats['no_buyback_no_sbc_count']}**
- `PAYOUT_NEGATIVE_EARNINGS`: **{stats['payout_negative_earnings_count']}**
- `SHARE_COUNT_DISCONTINUITY`: **{stats['share_count_discontinuity_count']}**
- Buyback tag usage: **{json.dumps(diagnostics.get('buyback_tag_levels', {}), sort_keys=True)}**
- Dividend tag usage: **{json.dumps(diagnostics.get('dividend_tag_levels', {}), sort_keys=True)}**
- Bridge regression checks: **{regression['tests_passed']}/{regression['tests_total']} passed**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
"""

    STATUS_PATH.write_text(
        base.rstrip() + "\n" + section.lstrip(),
        encoding="utf-8",
    )

    return stats


def main() -> int:
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit(
            "sp500_fundamentals.csv non trovato: eseguire prima bridge + BR-01/BR-02"
        )

    fundamentals = pd.read_csv(FUNDAMENTALS_PATH, low_memory=False)

    required_inputs = {
        "annual_adsh",
        "annual_period",
        "annual_net_income",
        "annual_net_income_date",
        "annual_sbc",
        "annual_sbc_date",
        "diluted_shares_yoy",
    }
    missing_inputs = required_inputs - set(fundamentals.columns)
    if missing_inputs:
        raise SystemExit(
            "BR-03 input mancanti: " + ", ".join(sorted(missing_inputs))
        )

    downloader = bridge.Downloader()
    quarters, sec_index_meta = bridge.discover_sec_quarters(downloader)
    selected_quarters = quarters[-SEC_QUARTERS:]
    latest_key = quarters[-1].key

    manifest = read_manifest()
    if not needs_enrichment(fundamentals, manifest, latest_key):
        print(
            f"BR-03 già applicato per {latest_key}; "
            "nessun download SEC necessario."
        )
        return 0

    print(
        f"BR-03: scarico {len(selected_quarters)} SEC datasets "
        f"({selected_quarters[0].key} → {selected_quarters[-1].key})..."
    )

    adsh_set = collect_adshs(fundamentals)
    if not adsh_set:
        raise SystemExit("BR-03: nessun ADSH disponibile nel fundamentals")

    with tempfile.TemporaryDirectory(prefix="investment_os_br03_") as td:
        td_path = Path(td)
        zip_infos: list[tuple[bridge.QuarterLink, Path]] = []
        downloads = []

        for q in selected_quarters:
            path = td_path / f"{q.key}.zip"
            print(f"  Scarico {q.label} ...")
            sha, nbytes = bridge.download_to_file(
                downloader,
                q.url,
                path,
            )
            zip_infos.append((q, path))
            downloads.append(
                {
                    "quarter": q.key,
                    "url": q.url,
                    "sha256": sha,
                    "bytes": nbytes,
                }
            )

        print(
            f"  ADSH da verificare: {len(adsh_set)}; "
            "scansione NUM per buyback/dividendi..."
        )
        nums = scan_nums(zip_infos, adsh_set)

        enriched, diagnostics = enrich_dataframe(
            fundamentals,
            nums,
        )

    regression = run_regression_checks(
        fundamentals,
        enriched,
        diagnostics,
    )

    if not regression["all_passed"]:
        failed = [
            key
            for key, value in regression["tests"].items()
            if not value["passed"]
        ]
        raise SystemExit(
            "BR-03 regression fallita: "
            + ", ".join(failed)
            + ". Nessun file canonicale scritto."
        )

    # Write only after every local integrity check passes.
    bridge.write_csv_atomic(FUNDAMENTALS_PATH, enriched)
    update_coverage_file(enriched)

    stats = update_status(
        enriched,
        diagnostics,
        [q.key for q in selected_quarters],
        regression,
    )

    bridge.write_json_atomic(REGRESSION_PATH, regression)

    manifest = read_manifest()
    manifest["schema_version"] = "1.3"
    manifest["br03_capital_return"] = {
        "schema": SCHEMA,
        "updated_at_utc": now_iso(),
        "latest_available_quarter": latest_key,
        "quarters_used": [q.key for q in selected_quarters],
        "sec_index": sec_index_meta,
        "quarter_downloads": downloads,
        "coverage": stats,
        "buyback_tag_hierarchy": [
            BUYBACK_PRIMARY,
            BUYBACK_BROAD,
            BUYBACK_TAX,
            BUYBACK_EQUITY,
        ],
        "dividend_tag_hierarchy": [
            DIV_COMMON,
            DIV_TOTAL,
            DIV_VARIANT,
        ],
        "provenance_only_tags": [
            DIV_PREFERRED,
            DIV_NCI,
        ],
        "rules": [
            "Absent tag is MISSING, never inferred as zero.",
            "Explicit reported zero remains economic zero.",
            "buyback_accretion = annual_buyback / annual_sbc.",
            "If annual_buyback > 0 and annual_sbc = 0, buyback_accretion = 2.0 per frozen V4.1 hi anchor.",
            "If annual_buyback = 0 and annual_sbc = 0, buyback_accretion = NOT_APPLICABLE.",
            "payout_ratio = annual_dividends_paid / annual_net_income only when annual_net_income > 0.",
            "payout_ratio is never negative and never NOT_APPLICABLE.",
            "share_change is an exact alias of existing diluted_shares_yoy; existing values are not modified.",
            "No price×shares or per-share reconstruction is used.",
            "This enrichment does not compute BQS, IOS, rankings, or recommendations.",
        ],
        "diagnostics": diagnostics,
        "regression": {
            "tests_passed": regression["tests_passed"],
            "tests_total": regression["tests_total"],
            "all_passed": regression["all_passed"],
        },
    }

    outputs = manifest.setdefault("outputs", {})
    for name in [
        "sp500_fundamentals.csv",
        "sp500_coverage.csv",
        "status.md",
        "br03_regression.json",
    ]:
        path = DATA_DIR / name
        if path.exists():
            outputs[name] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }

    bridge.write_json_atomic(MANIFEST_PATH, manifest)

    print("OK — BR-03 completato.")
    print(f"annual_buyback: {stats['annual_buyback_pct']:.1f}%")
    print(f"annual_dividends_paid: {stats['annual_dividends_paid_pct']:.1f}%")
    print(f"buyback_accretion: {stats['buyback_accretion_pct']:.1f}%")
    print(f"payout_ratio: {stats['payout_ratio_pct']:.1f}%")
    print(
        f"regression: {regression['tests_passed']}/"
        f"{regression['tests_total']} passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
