#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-04 S1 candidate builder.

Implements S1 of BR04_DATA_CONTRACT_V4_1_POST_T00_R3.

What this script does
---------------------
1. Pins data/current/sp500_fundamentals.csv to the most recent valid
   BR04-T00-bis v1.1 evidence with the same base_canonical_sha256.
2. Downloads the same 16 SEC Financial Statement Data Sets used by the bridge.
3. Reads debt/cash/interest facts only from the current annual filing and from
   the required face statement (BS / IS / CF, inpth=0).
4. Builds BR-04 fields conservatively in staging.
5. Appends BR-04 columns to the canonical CSV while preserving every existing
   field as its original text; the old 212 columns are never numerically
   re-serialized.
6. Writes candidate/evidence/audit files only under:
      data/staging/br04/<run_id>/
7. Never modifies data/current/.

Important limitation carried forward from T00-bis
-------------------------------------------------
The SEC Financial Statement Data Sets PRE table does not expose the
parent-child presentation/calculation tree needed to prove every BS leaf versus
subtotal. Therefore strict §7.2 balance-sheet closure is NOT fabricated.
Consequences:
- absence of debt is never converted to zero;
- found debt remains PARTIAL unless a later authorized source proves closure;
- ROIC is not calculated from PARTIAL debt;
- the leverage-threshold interval logic (§8) is used to avoid favorable bias.

This is S1 only. It does NOT execute S2 regressions, S3 transport tests,
S4 engine tests, rankings, recommendations or the Blind Test.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import bridge


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DIR = ROOT / "data" / "current"
STAGING_BASE = ROOT / "data" / "staging" / "br04"

FUNDAMENTALS_PATH = CURRENT_DIR / "sp500_fundamentals.csv"
MANIFEST_PATH = CURRENT_DIR / "manifest.json"
STATUS_PATH = CURRENT_DIR / "status.md"

RUN_ID = (
    os.getenv("GITHUB_RUN_ID", "").strip()
    or datetime.now(timezone.utc).strftime("local_%Y%m%dT%H%M%SZ")
)
RUN_DIR = STAGING_BASE / RUN_ID
CANDIDATE_DIR = RUN_DIR / "candidate"
EVIDENCE_DIR = RUN_DIR / "evidence"
AUDIT_DIR = RUN_DIR / "audit"

CANDIDATE_PATH = CANDIDATE_DIR / "sp500_fundamentals.csv"
MANIFEST_CANDIDATE_PATH = CANDIDATE_DIR / "manifest_candidate.json"
STATUS_CANDIDATE_PATH = CANDIDATE_DIR / "status_candidate.md"
BUILD_REPORT_PATH = EVIDENCE_DIR / "br04_s1_build.json"
DIFF_PATH = EVIDENCE_DIR / "br04_diff_vs_current.json"
COMPONENTS_PATH = EVIDENCE_DIR / "br04_components.csv"
CUSTOM_AUDIT_PATH = AUDIT_DIR / "br04_custom_lines_audit.csv"
INDETERMINATE_PATH = AUDIT_DIR / "br04_indeterminate_rows.csv"

SEC_QUARTERS = 16
SCHEMA = "br04_debt_interest_v1.0"
LABEL_DICTIONARY_VERSION = "br04_label_v1.0"
CLOSURE_SUPPORTED = False
LEVERAGE_THRESHOLD = 3.0
RECON_TOL = 0.005


# ---------------------------------------------------------------------------
# Frozen V4.1 module mapping for the modules that BR-04 treats specially.
# These SIC sets reproduce the current 504-row preflight counts:
# BANK 20, ASSETMGR_EXCH 19, INSURANCE 29, REIT 30, UTILITY 37.
# ---------------------------------------------------------------------------
BANK_SICS = {6021, 6022, 6199}
ASSETMGR_EXCH_SICS = {6200, 6211, 6282}
INSURANCE_SICS = {6311, 6321, 6324, 6331, 6399, 6411}
REIT_SICS = {6500, 6510, 6792, 6798}
UTILITY_SICS = {4911, 4922, 4923, 4924, 4931, 4932, 4941, 4953, 4991}


# ---------------------------------------------------------------------------
# Frozen BR-04 tag sets.
# ---------------------------------------------------------------------------
CURRENT_COMPONENT_TAGS = {
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "CommercialPaper",
    "LinesOfCreditCurrent",
    "NotesPayableCurrent",
    "SecuredDebtCurrent",
    "UnsecuredDebtCurrent",
    "ConvertibleNotesPayableCurrent",
    "OtherShortTermBorrowings",
}
CURRENT_AGGREGATE_TAGS = {
    "DebtCurrent",
    "LongTermDebtAndCapitalLeaseObligationsCurrent",
}

NONCURRENT_COMPONENT_TAGS = {
    "LongTermNotesPayable",
    "SeniorLongTermNotes",
    "ConvertibleLongTermNotesPayable",
    "LongTermLineOfCredit",
    "OtherLongTermDebtNoncurrent",
    "SecuredLongTermDebt",
    "UnsecuredLongTermDebt",
    "SecuredDebt",
    "UnsecuredDebt",
    "NotesPayable",
}
NONCURRENT_AGGREGATE_TAGS = {
    "LongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebt",
}

FULL_DEBT_AGGREGATE_TAGS = {
    "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
    "DebtAndCapitalLeaseObligations",
    "DebtLongtermAndShorttermCombinedAmount",
}

FINANCE_LEASE_CURRENT = {"FinanceLeaseLiabilityCurrent"}
FINANCE_LEASE_NONCURRENT = {"FinanceLeaseLiabilityNoncurrent"}
FINANCE_LEASE_AGGREGATE = {"FinanceLeaseLiability"}

OPERATING_LEASE_CURRENT = {"OperatingLeaseLiabilityCurrent"}
OPERATING_LEASE_NONCURRENT = {"OperatingLeaseLiabilityNoncurrent"}
OPERATING_LEASE_AGGREGATE = {"OperatingLeaseLiability"}

CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "Cash",
]
STI_TAGS = [
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
]
LIABILITY_TAGS = [
    "Liabilities",
    "LiabilitiesAndStockholdersEquity",
    "StockholdersEquity",
]

GROSS_INTEREST_L1 = [
    "InterestExpenseNonoperating",
    "InterestExpense",
]
GROSS_INTEREST_L2 = [
    "InterestExpenseDebt",
    "InterestAndDebtExpense",
]
NET_INTEREST_TAGS = [
    "InterestIncomeExpenseNonoperatingNet",
    "InterestIncomeExpenseNet",
    "InterestRevenueExpenseNet",
]
INTEREST_PAID_TAG = "InterestPaidNet"
INTEREST_INCOME_TAG = "InvestmentIncomeInterest"

LEGACY_FORBIDDEN_TAGS = {
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
}

MORTGAGE_ASSET_TAGS = {
    "MortgageLoansOnRealEstate",
}

STANDARD_TAGS = (
    CURRENT_COMPONENT_TAGS
    | CURRENT_AGGREGATE_TAGS
    | NONCURRENT_COMPONENT_TAGS
    | NONCURRENT_AGGREGATE_TAGS
    | FULL_DEBT_AGGREGATE_TAGS
    | FINANCE_LEASE_CURRENT
    | FINANCE_LEASE_NONCURRENT
    | FINANCE_LEASE_AGGREGATE
    | OPERATING_LEASE_CURRENT
    | OPERATING_LEASE_NONCURRENT
    | OPERATING_LEASE_AGGREGATE
    | set(CASH_TAGS)
    | set(STI_TAGS)
    | set(LIABILITY_TAGS)
    | set(GROSS_INTEREST_L1)
    | set(GROSS_INTEREST_L2)
    | set(NET_INTEREST_TAGS)
    | {INTEREST_PAID_TAG, INTEREST_INCOME_TAG}
    | LEGACY_FORBIDDEN_TAGS
    | MORTGAGE_ASSET_TAGS
)

DEBT_LABEL_RE = re.compile(
    r"\b("
    r"debt|borrow(?:ing|ings)?|notes?\s+payable|senior\s+notes?|"
    r"loan(?:s)?|credit\s+facilit(?:y|ies)|revolving|commercial\s+paper|"
    r"term\s+loan|bonds?|debentures?|finance\s+lease|"
    r"financing\s+obligation|securiti[sz]ation"
    r")\b",
    flags=re.I,
)

NON_DEBT_LABEL_RE = re.compile(
    r"\b("
    r"accounts?\s+payable|accrued|deferred\s+revenue|contract\s+liabilit|"
    r"income\s+tax|deferred\s+tax|pension|postretirement|warranty|"
    r"restructuring|customer\s+deposit|contingent\s+consideration|"
    r"derivative\s+liabilit|deferred\s+compensation|dividends?\s+payable|"
    r"operating\s+lease|asset\s+retirement|environmental|self[-\s]?insurance|"
    r"regulatory\s+liabilit"
    r")\b",
    flags=re.I,
)

EQUITY_HINT_RE = re.compile(
    r"\b("
    r"common\s+stock|preferred\s+stock|additional\s+paid[-\s]?in\s+capital|"
    r"paid[-\s]?in\s+capital|retained\s+earnings|accumulated\s+deficit|"
    r"treasury\s+stock|stockholders?\s+equity|shareholders?\s+equity|"
    r"members?\s+equity|partners?\s+capital|noncontrolling\s+interest|"
    r"minority\s+interest|temporary\s+equity|accumulated\s+other\s+comprehensive"
    r")\b",
    flags=re.I,
)

AFUDC_RE = re.compile(r"\bAFUDC\b|allowance for funds used during construction", re.I)
SECURITIZATION_RE = re.compile(r"securiti[sz]ation|transition bond", re.I)


# ---------------------------------------------------------------------------
# Candidate columns. Existing columns are never rewritten numerically.
# ---------------------------------------------------------------------------
VALUE_COLUMNS = [
    "current_debt",
    "long_term_debt",
    "finance_lease_liabilities",
    "total_debt",
    "total_debt_candidates",
    "cash_and_equivalents",
    "short_term_investments",
    "operating_lease_liabilities",
    "total_liabilities",
    "net_debt",
    "net_debt_to_ocf",
    "net_debt_to_ocf_lb",
    "net_debt_to_ocf_ub",
    "net_debt_to_ocf_ub_no_cash",
    "interest_expense",
    "total_liabilities_and_equity",
    "bs_closure_residual_pct",
    "debt_classification_method",
    "label_dictionary_version",
    "interest_coverage",
    "invested_capital",
    "roic",
    "ios_leverage_indeterminate",
]

STATUS_COLUMNS = [
    "total_debt_status",
    "interest_status",
    "br04_status",
    "br04_flags",
    "br04_module",
    "br04_source_quarters",
    "br04_legacy_comparison_note",
]

AGG_COMPONENT_COLUMNS = [
    "current_debt_components",
    "long_term_debt_components",
    "finance_lease_liabilities_components",
    "total_debt_components",
    "operating_lease_liabilities_components",
    "total_liabilities_components",
    "interest_expense_components",
]

SINGLE_FACT_FIELDS = [
    "cash_and_equivalents",
    "short_term_investments",
    "total_liabilities_and_equity",
    "interest_expense",
]
PROV_SUFFIXES = [
    "_tag",
    "_version",
    "_adsh",
    "_ddate",
    "_qtrs",
    "_uom",
    "_stmt",
    "_line",
    "_plabel",
]

PROVENANCE_COLUMNS = [
    field + suffix
    for field in SINGLE_FACT_FIELDS
    for suffix in PROV_SUFFIXES
]

BR04_COLUMNS = VALUE_COLUMNS + STATUS_COLUMNS + AGG_COMPONENT_COLUMNS + PROVENANCE_COLUMNS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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


def finite_number(value) -> float | None:
    if value is None:
        return None
    text = norm_text(value)
    if not text or text.upper() in {"MISSING", "CONFLICTING", "NOT_APPLICABLE"}:
        return None
    try:
        x = float(text)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def fmt_num(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    if abs(float(value)) < 5e-15:
        return "0"
    return format(float(value), ".15g")


def approx_equal(a: float, b: float, tol: float = RECON_TOL) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale <= tol


def classify_module(sic_value) -> str:
    sic = finite_number(sic_value)
    if sic is None:
        return "UNKNOWN"
    s = int(sic)
    if s in BANK_SICS:
        return "BANK"
    if s in ASSETMGR_EXCH_SICS:
        return "ASSETMGR_EXCH"
    if s in INSURANCE_SICS:
        return "INSURANCE"
    if s in REIT_SICS:
        return "REIT"
    if s in UTILITY_SICS:
        return "UTILITY"
    return "OTHER"


def classify_custom_label(label: str) -> str:
    if DEBT_LABEL_RE.search(label or ""):
        return "CUSTOM_DEBT"
    if NON_DEBT_LABEL_RE.search(label or ""):
        return "CUSTOM_NON_DEBT"
    if EQUITY_HINT_RE.search(label or ""):
        return "CUSTOM_EQUITY_HINT"
    return "UNCLASSIFIED"


def read_tsv_member(zf: zipfile.ZipFile, filename: str, **kwargs) -> pd.DataFrame:
    names = {name.lower(): name for name in zf.namelist()}
    actual = names.get(filename.lower())
    if not actual:
        raise bridge.BridgeError(f"{filename} non presente nel dataset SEC")
    with zf.open(actual) as f:
        return pd.read_csv(
            f,
            sep="\t",
            dtype=str,
            low_memory=False,
            **kwargs,
        )


def read_canonical_raw() -> tuple[list[str], list[list[str]], list[str]]:
    """
    Return header, parsed rows and original physical lines without line endings.

    S1 is intentionally strict: if a record spans multiple physical lines, stop
    instead of normalizing/re-serializing the existing canonical columns.
    """
    raw = FUNDAMENTALS_PATH.read_text(encoding="utf-8")
    physical = raw.splitlines()
    if not physical:
        raise SystemExit("Canonico vuoto")

    header = next(csv.reader([physical[0]]))
    rows: list[list[str]] = []
    raw_rows: list[str] = []

    for line_no, line in enumerate(physical[1:], start=2):
        if not line:
            continue
        parsed = next(csv.reader([line]))
        if len(parsed) != len(header):
            raise SystemExit(
                f"S1_BLOCK: riga fisica {line_no} ha {len(parsed)} colonne, "
                f"attese {len(header)}. Possibile newline embedded: non "
                f"riscrivere il canonico."
            )
        rows.append(parsed)
        raw_rows.append(line)

    if len(rows) != 504:
        raise SystemExit(f"S1_BLOCK: righe canoniche={len(rows)}, attese 504")
    if len(header) != 212:
        raise SystemExit(f"S1_BLOCK: colonne base={len(header)}, attese 212")

    if any(col in header for col in BR04_COLUMNS):
        raise SystemExit("S1_BLOCK: colonne BR-04 già presenti nel canonico")

    return header, rows, raw_rows


def latest_valid_t00bis(base_sha: str) -> tuple[Path, dict]:
    candidates: list[tuple[float, Path, dict]] = []

    if not STAGING_BASE.exists():
        raise SystemExit("S1_BLOCK: staging BR-04 assente; eseguire T00-bis")

    for path in STAGING_BASE.glob("*/evidence/br04_t00bis_report.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if payload.get("schema") != "br04_t00bis_probe_v1.2":
            continue
        if payload.get("base_canonical_sha256") != base_sha:
            continue
        if payload.get("candidate_sha256") is not None:
            continue

        candidates.append((path.stat().st_mtime, path, payload))

    if not candidates:
        raise SystemExit(
            "S1_BLOCK: nessun T00-bis v1.1 valido con lo stesso "
            "base_canonical_sha256. Rieseguire Probe BR-04 T00-bis."
        )

    _, path, payload = max(candidates, key=lambda item: item[0])
    return path, payload


def csv_fragment(values: list[str]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="")
    writer.writerow(values)
    return buf.getvalue()


def fact_key(adsh: str, tag: str, version: str) -> tuple[str, str, str]:
    return adsh, tag, version


def usable_fact(
    num_rows: pd.DataFrame,
    *,
    adsh: str,
    tag: str,
    version: str,
    annual_period: str,
    qtrs_required: int,
) -> tuple[str, dict | None]:
    """
    Returns status and one fact:
      OK / MISSING / CONFLICTING.
    """
    work = num_rows[
        num_rows["adsh"].astype(str).eq(adsh)
        & num_rows["tag"].astype(str).eq(tag)
    ].copy()

    if "version" in work.columns and version:
        exact_version = work[work["version"].fillna("").astype(str).eq(version)]
        if not exact_version.empty:
            work = exact_version

    if work.empty:
        return "MISSING", None

    if "ddate_norm" not in work.columns:
        work["ddate_norm"] = work["ddate"].map(norm_date)

    work = work[work["ddate_norm"].eq(annual_period)]
    if work.empty:
        return "MISSING", None

    if "qtrs_num" not in work.columns:
        work["qtrs_num"] = pd.to_numeric(work.get("qtrs"), errors="coerce")
    work = work[work["qtrs_num"].eq(qtrs_required)]
    if work.empty:
        return "MISSING", None

    if "coreg" in work.columns:
        work = work[work["coreg"].fillna("").eq("")]
    if "segments" in work.columns:
        work = work[work["segments"].fillna("").eq("")]
    if work.empty:
        return "MISSING", None

    work["value_num"] = pd.to_numeric(work.get("value"), errors="coerce")
    work = work[work["value_num"].notna()]
    if work.empty:
        return "MISSING", None

    uoms = sorted(
        {norm_text(x).upper() for x in work.get("uom", pd.Series(dtype=str)) if norm_text(x)}
    )
    if len(uoms) > 1:
        return "CONFLICTING", None
    if uoms and uoms[0] != "USD":
        return "CONFLICTING", None

    unique_values = sorted({float(x) for x in work["value_num"].tolist()})
    if len(unique_values) > 1:
        return "CONFLICTING", None

    row = work.iloc[-1]
    fact = {
        "value": float(unique_values[0]),
        "tag": tag,
        "version": norm_text(row.get("version")) or version,
        "adsh": adsh,
        "ddate": norm_date(row.get("ddate")),
        "qtrs": norm_text(row.get("qtrs")),
        "uom": norm_text(row.get("uom")),
    }
    return "OK", fact


def fact_with_face(
    line: dict,
    fact: dict,
) -> dict:
    out = dict(fact)
    out.update(
        {
            "stmt": line["stmt"],
            "line": line["line"],
            "plabel": line["plabel"],
            "class": line["class"],
        }
    )
    return out


def make_component_string(items: list[dict]) -> str:
    # Deterministic serialization: component provenance must not depend on
    # Python set/dict iteration order or source-row ordering across runs.
    ordered = sorted(
        items,
        key=lambda item: (
            str(item.get("tag", "")),
            float(item.get("value", 0.0)),
            str(item.get("line", "")),
            str(item.get("version", "")),
        ),
    )
    return ";".join(
        f"{item['tag']}={fmt_num(item['value'])}"
        for item in ordered
    )


def sum_items(items: list[dict]) -> float | None:
    if not items:
        return None
    return sum(float(item["value"]) for item in items)


def first_by_hierarchy(
    facts_by_tag: dict[str, list[dict]],
    tags: list[str],
) -> dict | None:
    for tag in tags:
        items = facts_by_tag.get(tag, [])
        if not items:
            continue
        # There should normally be one face line per tag; if multiple identical
        # values exist, retain the last presentation line deterministically.
        return items[-1]
    return None


def provenance_values(fact: dict | None) -> dict[str, str]:
    if fact is None:
        return {
            "_tag": "",
            "_version": "",
            "_adsh": "",
            "_ddate": "",
            "_qtrs": "",
            "_uom": "",
            "_stmt": "",
            "_line": "",
            "_plabel": "",
        }
    return {
        "_tag": fact.get("tag", ""),
        "_version": fact.get("version", ""),
        "_adsh": fact.get("adsh", ""),
        "_ddate": fact.get("ddate", ""),
        "_qtrs": fact.get("qtrs", ""),
        "_uom": fact.get("uom", ""),
        "_stmt": fact.get("stmt", ""),
        "_line": fact.get("line", ""),
        "_plabel": fact.get("plabel", ""),
    }


def choose_group_lower_bound(
    *,
    leaf_items: list[dict],
    aggregate_items: list[dict],
    group_name: str,
    flags: set[str],
) -> tuple[float | None, list[dict], list[str]]:
    """
    Conservative anti-double-counting group value.

    We never sum an aggregate with its components. Candidate values are:
    - component sum, if components exist;
    - each aggregate value.
    The largest candidate is retained as a conservative debt lower-bound.
    Material disagreement is recorded, but because strict BS closure is not
    available in FSDS the group remains part of a PARTIAL total rather than
    inventing exactness.
    """
    candidates: list[tuple[str, float, list[dict]]] = []

    if leaf_items:
        value = sum_items(leaf_items)
        if value is not None:
            candidates.append((f"{group_name}_COMPONENTS", value, leaf_items))

    for item in aggregate_items:
        candidates.append((item["tag"], float(item["value"]), [item]))

    if not candidates:
        return None, [], []

    values = [x[1] for x in candidates]
    lo = min(values)
    hi = max(values)
    if len(values) > 1 and not approx_equal(lo, hi):
        flags.add("BS_CLOSURE_FAILED")

    chosen = max(candidates, key=lambda x: x[1])
    descriptions = [f"{name}={fmt_num(value)}" for name, value, _ in candidates]
    return chosen[1], chosen[2], descriptions


def write_components(rows: list[dict]) -> None:
    COMPONENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "ticker",
        "adsh",
        "stmt",
        "line",
        "plabel",
        "tag",
        "version",
        "class",
        "value",
        "ddate",
        "qtrs",
        "uom",
        "used_as",
    ]
    with COMPONENTS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in columns})


def write_custom_audit(rows: list[dict]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    columns = [
        "ticker",
        "adsh",
        "line",
        "plabel",
        "tag",
        "version",
        "assigned_class",
        "value",
        "ddate",
        "uom",
    ]
    with CUSTOM_AUDIT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in columns})


def main() -> int:
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit("S1_BLOCK: sp500_fundamentals.csv non trovato")

    base_sha = sha256_file(FUNDAMENTALS_PATH)
    header, parsed_rows, raw_rows = read_canonical_raw()
    idx = {name: i for i, name in enumerate(header)}

    required_base = {
        "ticker",
        "sic",
        "annual_period",
        "annual_adsh",
        "annual_operating_cash_flow",
        "annual_operating_income",
        "annual_equity",
        "annual_cash",
        "annual_cash_tag",
        "annual_debt",
    }
    missing_base = required_base - set(header)
    if missing_base:
        raise SystemExit(
            "S1_BLOCK: colonne base mancanti: " + ", ".join(sorted(missing_base))
        )

    t00_path, t00 = latest_valid_t00bis(base_sha)
    source_t00_run_id = str(t00.get("run_id", ""))

    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # Copy S0 evidence into the S1 custody directory, byte-for-byte.
    shutil.copy2(t00_path, EVIDENCE_DIR / "br04_t00bis_report.json")
    t00_md = t00_path.with_suffix(".md")
    if t00_md.exists():
        shutil.copy2(t00_md, EVIDENCE_DIR / "br04_t00bis_report.md")

    annual_meta: dict[str, dict] = {}
    for row in parsed_rows:
        adsh = norm_text(row[idx["annual_adsh"]])
        if not adsh:
            continue
        annual_meta[adsh] = {
            "ticker": norm_text(row[idx["ticker"]]),
            "period": norm_date(row[idx["annual_period"]]),
        }

    annual_adshs = set(annual_meta)

    downloader = bridge.Downloader()
    quarters, sec_index_meta = bridge.discover_sec_quarters(downloader)
    selected_quarters = quarters[-SEC_QUARTERS:]

    face_lines: dict[str, list[dict]] = defaultdict(list)
    num_frames: list[pd.DataFrame] = []
    all_custom_audit: list[dict] = []

    print(
        f"BR04 S1: base_sha={base_sha}, T00-bis run={source_t00_run_id}, "
        f"annual_adsh={len(annual_adshs)}"
    )

    with tempfile.TemporaryDirectory(prefix="investment_os_br04_s1_") as td:
        td_path = Path(td)

        for q in selected_quarters:
            zip_path = td_path / f"{q.key}.zip"
            print(f"  Scarico {q.label} ...")
            bridge.download_to_file(downloader, q.url, zip_path)

            with zipfile.ZipFile(zip_path) as zf:
                pre = read_tsv_member(
                    zf,
                    "pre.txt",
                    usecols=lambda c: c in {
                        "adsh",
                        "report",
                        "line",
                        "stmt",
                        "inpth",
                        "tag",
                        "version",
                        "plabel",
                    },
                )
                pre = pre[pre["adsh"].isin(annual_adshs)].copy()
                pre["stmt"] = pre["stmt"].fillna("").str.upper().str.strip()
                pre["inpth"] = pd.to_numeric(pre["inpth"], errors="coerce")
                face = pre[
                    pre["stmt"].isin({"BS", "IS", "CF"})
                    & pre["inpth"].fillna(0).eq(0)
                ].copy()

                tagdf = read_tsv_member(
                    zf,
                    "tag.txt",
                    usecols=lambda c: c in {"tag", "version", "custom"},
                )
                tagdf["custom"] = pd.to_numeric(
                    tagdf.get("custom"),
                    errors="coerce",
                )
                custom_pairs = set(
                    zip(
                        tagdf.loc[tagdf["custom"].eq(1), "tag"].fillna(""),
                        tagdf.loc[tagdf["custom"].eq(1), "version"].fillna(""),
                    )
                )

                custom_tags_this_zip: set[str] = set()

                for _, r in face.iterrows():
                    adsh = norm_text(r.get("adsh"))
                    tag = norm_text(r.get("tag"))
                    version = norm_text(r.get("version"))
                    stmt = norm_text(r.get("stmt")).upper()
                    plabel = norm_text(r.get("plabel"))
                    line_no = norm_text(r.get("line"))

                    is_custom = (tag, version) in custom_pairs

                    line_class = ""
                    required_stmt = ""

                    if is_custom and stmt == "BS":
                        line_class = classify_custom_label(plabel)
                        required_stmt = "BS"
                        custom_tags_this_zip.add(tag)
                    elif tag in FINANCE_LEASE_CURRENT | FINANCE_LEASE_NONCURRENT | FINANCE_LEASE_AGGREGATE:
                        line_class = "FINANCE_LEASE"
                        required_stmt = "BS"
                    elif tag in CURRENT_COMPONENT_TAGS:
                        line_class = "CURRENT_DEBT"
                        required_stmt = "BS"
                    elif tag in CURRENT_AGGREGATE_TAGS:
                        line_class = "CURRENT_DEBT_AGGREGATE"
                        required_stmt = "BS"
                    elif tag in NONCURRENT_COMPONENT_TAGS:
                        line_class = "NONCURRENT_DEBT"
                        required_stmt = "BS"
                    elif tag in NONCURRENT_AGGREGATE_TAGS:
                        line_class = "NONCURRENT_DEBT_AGGREGATE"
                        required_stmt = "BS"
                    elif tag in FULL_DEBT_AGGREGATE_TAGS:
                        line_class = "DEBT_AGGREGATE"
                        required_stmt = "BS"
                    elif tag in OPERATING_LEASE_CURRENT | OPERATING_LEASE_NONCURRENT | OPERATING_LEASE_AGGREGATE:
                        line_class = "OPERATING_LEASE"
                        required_stmt = "BS"
                    elif tag in set(CASH_TAGS):
                        line_class = "CASH"
                        required_stmt = "BS"
                    elif tag in set(STI_TAGS):
                        line_class = "STI"
                        required_stmt = "BS"
                    elif tag in set(LIABILITY_TAGS):
                        line_class = "BALANCE_CONTROL"
                        required_stmt = "BS"
                    elif tag in set(GROSS_INTEREST_L1) | set(GROSS_INTEREST_L2):
                        line_class = "GROSS_INTEREST"
                        required_stmt = "IS"
                    elif tag in set(NET_INTEREST_TAGS):
                        line_class = "NET_INTEREST"
                        required_stmt = "IS"
                    elif tag == INTEREST_INCOME_TAG:
                        line_class = "INTEREST_INCOME"
                        required_stmt = "IS"
                    elif tag == INTEREST_PAID_TAG:
                        line_class = "INTEREST_PAID"
                        required_stmt = "CF"
                    elif tag in LEGACY_FORBIDDEN_TAGS:
                        line_class = "LEGACY_FORBIDDEN"
                        required_stmt = "BS"
                    elif tag in MORTGAGE_ASSET_TAGS:
                        line_class = "MORTGAGE_ASSET"
                        required_stmt = "BS"
                    else:
                        continue

                    if stmt != required_stmt:
                        continue

                    face_lines[adsh].append(
                        {
                            "adsh": adsh,
                            "tag": tag,
                            "version": version,
                            "stmt": stmt,
                            "line": line_no,
                            "plabel": plabel,
                            "class": line_class,
                            "sec_source_quarter": q.key,
                        }
                    )

                # NUM scan: standard tags + custom face tags found in this zip.
                wanted_tags = set(STANDARD_TAGS) | custom_tags_this_zip
                names = {name.lower(): name for name in zf.namelist()}
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
                        mask = (
                            chunk["adsh"].isin(annual_adshs)
                            & chunk["tag"].isin(wanted_tags)
                        )
                        if "coreg" in chunk.columns:
                            mask &= chunk["coreg"].fillna("").eq("")
                        if "segments" in chunk.columns:
                            mask &= chunk["segments"].fillna("").eq("")

                        part = chunk.loc[mask].copy()
                        if part.empty:
                            continue
                        part["sec_source_quarter"] = q.key
                        part["ddate_norm"] = part.get(
                            "ddate",
                            pd.Series(index=part.index, dtype=str),
                        ).map(norm_date)
                        part["qtrs_num"] = pd.to_numeric(
                            part.get("qtrs"),
                            errors="coerce",
                        )
                        num_frames.append(part)

    if num_frames:
        nums = pd.concat(num_frames, ignore_index=True, sort=False)
    else:
        nums = pd.DataFrame(
            columns=[
                "adsh",
                "tag",
                "version",
                "ddate",
                "qtrs",
                "uom",
                "value",
                "coreg",
                "segments",
                "ddate_norm",
                "qtrs_num",
            ]
        )

    result_by_ticker: dict[str, dict[str, str]] = {}
    components_out: list[dict] = []
    indeterminate_out: list[dict] = []

    module_counts = defaultdict(int)
    state_counts = defaultdict(int)
    flag_counts = defaultdict(int)

    for base_row in parsed_rows:
        ticker = norm_text(base_row[idx["ticker"]])
        adsh = norm_text(base_row[idx["annual_adsh"]])
        period = norm_date(base_row[idx["annual_period"]])
        module = classify_module(base_row[idx["sic"]])
        module_counts[module] += 1

        flags: set[str] = set()
        values: dict[str, str] = {col: "" for col in BR04_COLUMNS}
        values["label_dictionary_version"] = LABEL_DICTIONARY_VERSION
        values["br04_module"] = module
        values["br04_source_quarters"] = (
            f"{selected_quarters[0].key}:{selected_quarters[-1].key}"
        )
        values["ios_leverage_indeterminate"] = "false"

        if not adsh:
            flags.add("NO_ANNUAL_ADSH")
            values["total_debt_status"] = "MISSING"
            values["interest_status"] = "MISSING"
            values["br04_status"] = "MISSING"
            values["br04_flags"] = ";".join(sorted(flags))
            result_by_ticker[ticker] = values
            state_counts["MISSING"] += 1
            continue

        flags.add("FSDS_FACE_ONLY")

        lines = face_lines.get(adsh, [])
        facts_by_tag: dict[str, list[dict]] = defaultdict(list)
        missing_face_value = False
        conflicting_fact = False
        custom_unclassified = False
        custom_debt_used = False
        mortgage_asset_seen = False
        afudc_seen = False
        utility_securitization_seen = False

        for line in lines:
            if line["class"] == "LEGACY_FORBIDDEN":
                flags.add("LEGACY_TAG_OBSERVED")
                conflicting_fact = True
                continue

            if line["class"] == "MORTGAGE_ASSET":
                mortgage_asset_seen = True

            if AFUDC_RE.search(line["plabel"]):
                afudc_seen = True
            if SECURITIZATION_RE.search(line["plabel"]):
                utility_securitization_seen = True

            qtrs_required = 0 if line["stmt"] == "BS" else 4
            status, fact = usable_fact(
                nums,
                adsh=adsh,
                tag=line["tag"],
                version=line["version"],
                annual_period=period,
                qtrs_required=qtrs_required,
            )

            if status == "CONFLICTING":
                conflicting_fact = True
                continue

            if status == "MISSING":
                # Face debt lines without usable value explicitly degrade debt.
                if line["class"] in {
                    "CURRENT_DEBT",
                    "CURRENT_DEBT_AGGREGATE",
                    "NONCURRENT_DEBT",
                    "NONCURRENT_DEBT_AGGREGATE",
                    "DEBT_AGGREGATE",
                    "FINANCE_LEASE",
                    "CUSTOM_DEBT",
                }:
                    missing_face_value = True
                    flags.add("FACE_LINE_VALUE_NOT_FOUND")
                continue

            assert fact is not None
            enriched = fact_with_face(line, fact)
            facts_by_tag[line["tag"]].append(enriched)

            if line["class"].startswith("CUSTOM_"):
                audit_row = {
                    "ticker": ticker,
                    "adsh": adsh,
                    "line": line["line"],
                    "plabel": line["plabel"],
                    "tag": line["tag"],
                    "version": line["version"],
                    "assigned_class": line["class"],
                    "value": fmt_num(fact["value"]),
                    "ddate": fact["ddate"],
                    "uom": fact["uom"],
                }
                all_custom_audit.append(audit_row)

                if line["class"] == "UNCLASSIFIED":
                    custom_unclassified = True
                    flags.add("CUSTOM_LINE_UNCLASSIFIED")

        # ---------------------------------------------------------------
        # Cash, STI, leases and controls.
        # ---------------------------------------------------------------
        cash_fact = first_by_hierarchy(facts_by_tag, CASH_TAGS)
        cash = float(cash_fact["value"]) if cash_fact else None
        if cash_fact:
            values["cash_and_equivalents"] = fmt_num(cash)
            for suffix, content in provenance_values(cash_fact).items():
                values["cash_and_equivalents" + suffix] = content

        sti_fact = first_by_hierarchy(facts_by_tag, STI_TAGS)
        sti = float(sti_fact["value"]) if sti_fact else None
        if sti_fact:
            values["short_term_investments"] = fmt_num(sti)
            for suffix, content in provenance_values(sti_fact).items():
                values["short_term_investments" + suffix] = content

        op_lease_items: list[dict] = []
        op_agg = [
            x for tag in OPERATING_LEASE_AGGREGATE for x in facts_by_tag.get(tag, [])
        ]
        if op_agg:
            op_lease_items = [max(op_agg, key=lambda x: float(x["value"]))]
        else:
            op_lease_items = [
                x
                for tag in (OPERATING_LEASE_CURRENT | OPERATING_LEASE_NONCURRENT)
                for x in facts_by_tag.get(tag, [])
            ]
        op_lease = sum_items(op_lease_items)
        if op_lease is not None:
            values["operating_lease_liabilities"] = fmt_num(op_lease)
            values["operating_lease_liabilities_components"] = make_component_string(
                op_lease_items
            )

        lse_fact = first_by_hierarchy(
            facts_by_tag,
            ["LiabilitiesAndStockholdersEquity"],
        )
        equity_fact = first_by_hierarchy(facts_by_tag, ["StockholdersEquity"])
        liab_fact = first_by_hierarchy(facts_by_tag, ["Liabilities"])

        lse = float(lse_fact["value"]) if lse_fact else None
        equity_control = float(equity_fact["value"]) if equity_fact else None
        total_liabilities = float(liab_fact["value"]) if liab_fact else None

        if total_liabilities is None and lse is not None and equity_control is not None:
            derived = lse - equity_control
            if derived >= 0:
                total_liabilities = derived
                values["total_liabilities_components"] = (
                    f"LiabilitiesAndStockholdersEquity={fmt_num(lse)};"
                    f"StockholdersEquity=-{fmt_num(equity_control)}"
                )
        elif total_liabilities is not None:
            values["total_liabilities_components"] = (
                f"Liabilities={fmt_num(total_liabilities)}"
            )

        if total_liabilities is not None:
            values["total_liabilities"] = fmt_num(total_liabilities)

        if lse_fact:
            values["total_liabilities_and_equity"] = fmt_num(lse)
            for suffix, content in provenance_values(lse_fact).items():
                values["total_liabilities_and_equity" + suffix] = content

        # ---------------------------------------------------------------
        # Debt groups.
        # ---------------------------------------------------------------
        current_leaf = [
            x for tag in CURRENT_COMPONENT_TAGS for x in facts_by_tag.get(tag, [])
        ]
        current_agg = [
            x for tag in CURRENT_AGGREGATE_TAGS for x in facts_by_tag.get(tag, [])
        ]
        current_value, current_used, current_candidates = choose_group_lower_bound(
            leaf_items=current_leaf,
            aggregate_items=current_agg,
            group_name="CURRENT",
            flags=flags,
        )

        noncurrent_leaf = [
            x for tag in NONCURRENT_COMPONENT_TAGS for x in facts_by_tag.get(tag, [])
        ]
        noncurrent_agg = [
            x for tag in NONCURRENT_AGGREGATE_TAGS for x in facts_by_tag.get(tag, [])
        ]
        noncurrent_value, noncurrent_used, noncurrent_candidates = (
            choose_group_lower_bound(
                leaf_items=noncurrent_leaf,
                aggregate_items=noncurrent_agg,
                group_name="NONCURRENT",
                flags=flags,
            )
        )

        fin_current = [
            x for tag in FINANCE_LEASE_CURRENT for x in facts_by_tag.get(tag, [])
        ]
        fin_noncurrent = [
            x for tag in FINANCE_LEASE_NONCURRENT for x in facts_by_tag.get(tag, [])
        ]
        fin_agg = [
            x for tag in FINANCE_LEASE_AGGREGATE for x in facts_by_tag.get(tag, [])
        ]
        if fin_agg:
            finance_items = [max(fin_agg, key=lambda x: float(x["value"]))]
        else:
            finance_items = fin_current + fin_noncurrent
        finance_value = sum_items(finance_items)

        full_agg_items = [
            x for tag in FULL_DEBT_AGGREGATE_TAGS for x in facts_by_tag.get(tag, [])
        ]

        custom_debt_items: list[dict] = []
        for line in lines:
            if line["class"] != "CUSTOM_DEBT":
                continue
            for fact in facts_by_tag.get(line["tag"], []):
                if (
                    fact["version"] == line["version"]
                    and fact["line"] == line["line"]
                ):
                    custom_debt_items.append(fact)

        if custom_debt_items:
            custom_debt_used = True
            flags.add("CUSTOM_TAG_DEBT_BY_LABEL")

        # Plausible non-double-counted lower-bound candidates.
        total_candidates: list[tuple[str, float, list[dict]]] = []

        component_items: list[dict] = []
        component_total = 0.0
        has_component_total = False

        if current_value is not None:
            component_total += current_value
            has_component_total = True
            component_items += current_used
        if noncurrent_value is not None:
            component_total += noncurrent_value
            has_component_total = True
            component_items += noncurrent_used

        # Add explicit finance lease only when not already represented by a
        # combined debt+lease aggregate in the chosen current/noncurrent lines.
        combined_used = any(
            x["tag"].startswith("LongTermDebtAndCapitalLeaseObligations")
            for x in component_items
        )
        if finance_value is not None and not combined_used:
            component_total += finance_value
            has_component_total = True
            component_items += finance_items

        if has_component_total:
            total_candidates.append(
                ("CURRENT_PLUS_NONCURRENT", component_total, component_items)
            )

        for item in full_agg_items:
            total_candidates.append(
                (item["tag"], float(item["value"]), [item])
            )

        # Custom debt is always retained in provenance. Without a presentation
        # tree we cannot prove whether a custom line is already included in a
        # standard aggregate. Taking max avoids double counting while ensuring
        # a large custom debt line cannot disappear from the lower bound.
        custom_sum = sum_items(custom_debt_items)
        if custom_sum is not None:
            total_candidates.append(
                ("CUSTOM_DEBT_LINES", custom_sum, custom_debt_items)
            )

        total_debt = None
        total_used: list[dict] = []
        if total_candidates:
            chosen = max(total_candidates, key=lambda x: x[1])
            total_debt = chosen[1]
            total_used = chosen[2]

        # BR04-T03: when a full-debt aggregate and the independently assembled
        # current+noncurrent amount coexist, disagreement beyond 0.5% is
        # CONFLICTING. Keep all candidates in provenance and never publish the
        # lower/favorable amount as exact debt.
        component_candidate = next(
            (
                value
                for name, value, _ in total_candidates
                if name == "CURRENT_PLUS_NONCURRENT"
            ),
            None,
        )
        full_aggregate_candidates = [
            value
            for name, value, _ in total_candidates
            if name in FULL_DEBT_AGGREGATE_TAGS
        ]
        if (
            component_candidate is not None
            and full_aggregate_candidates
            and any(
                not approx_equal(component_candidate, aggregate_value)
                for aggregate_value in full_aggregate_candidates
            )
        ):
            conflicting_fact = True
            flags.add("BS_CLOSURE_FAILED")

        # Strict closure is unavailable with current FSDS, so found debt cannot
        # be certified exact. Missing debt never becomes zero.
        if conflicting_fact or "LEGACY_TAG_OBSERVED" in flags:
            total_debt_status = "CONFLICTING"
        elif total_debt is not None:
            total_debt_status = "PARTIAL"
            flags.add("BS_CLOSURE_FAILED")
        else:
            total_debt_status = "MISSING"
            flags.add("BS_CLOSURE_FAILED")

        if missing_face_value and total_debt_status != "CONFLICTING":
            total_debt_status = "PARTIAL" if total_debt is not None else "MISSING"

        if custom_unclassified and total_debt_status != "CONFLICTING":
            total_debt_status = "PARTIAL" if total_debt is not None else "MISSING"

        values["total_debt_status"] = total_debt_status
        values["debt_classification_method"] = (
            "LABEL" if custom_debt_used else "TAG"
        )

        if current_value is not None:
            values["current_debt"] = fmt_num(current_value)
            values["current_debt_components"] = make_component_string(current_used)

        if noncurrent_value is not None:
            values["long_term_debt"] = fmt_num(noncurrent_value)
            values["long_term_debt_components"] = make_component_string(
                noncurrent_used
            )

        if finance_value is not None:
            values["finance_lease_liabilities"] = fmt_num(finance_value)
            values["finance_lease_liabilities_components"] = make_component_string(
                finance_items
            )

        # BR04-T01: without demonstrated §7.2 closure, an observed zero-valued
        # debt line is NOT evidence that enterprise debt is economically zero.
        # Preserve the zero candidate in provenance, but keep the motor-facing
        # total_debt cell blank.
        if (
            total_debt is not None
            and total_debt > 0
            and total_debt_status != "CONFLICTING"
        ):
            values["total_debt"] = fmt_num(total_debt)
        values["total_debt_components"] = make_component_string(total_used)
        values["total_debt_candidates"] = ";".join(
            f"{name}={fmt_num(val)}"
            for name, val, _ in total_candidates
        )

        # Historical debt comparison is diagnostic only; annual_debt remains
        # untouched in the first 212 columns.
        legacy_debt = finite_number(base_row[idx["annual_debt"]])
        if (
            total_debt is not None
            and legacy_debt is not None
            and legacy_debt > 0
            and total_debt < legacy_debt * (1.0 - RECON_TOL)
        ):
            flags.add("TOTAL_DEBT_BELOW_LEGACY")
            values["br04_legacy_comparison_note"] = (
                "BR04_FACE_ONLY_LOWER_BOUND_BELOW_LEGACY;"
                f"br04={fmt_num(total_debt)};"
                f"legacy={fmt_num(legacy_debt)};"
                "closure_unavailable=true"
            )

        if sti is not None and total_debt is not None and total_debt > 0:
            if sti > 0.10 * total_debt:
                flags.add("STI_NOT_NETTED")

        # Sector flags that do not alter the frozen module.
        sic_num = finite_number(base_row[idx["sic"]])
        sic_int = int(sic_num) if sic_num is not None else None
        if module == "ASSETMGR_EXCH" and sic_int == 6211:
            if facts_by_tag.get("ShortTermBorrowings"):
                flags.add("BROKER_DEALER_FUNDING")
        if module == "INSURANCE":
            flags.add("INSURER_OCF_INCLUDES_FLOAT")
        if module == "REIT":
            flags.add("REIT_BOOK_ROIC_DEPRECIATION_DISTORTED")
            if mortgage_asset_seen:
                flags.add("MORTGAGE_REIT_SUSPECTED")
        if module == "UTILITY":
            if utility_securitization_seen:
                flags.add("UTILITY_SECURITIZATION_INCLUDED")
            if afudc_seen and (
                facts_by_tag.get("InterestExpense")
                or facts_by_tag.get("InterestExpenseNonoperating")
            ):
                flags.add("UTILITY_INTEREST_NET_OF_AFUDC")

        # ---------------------------------------------------------------
        # Interest hierarchy.
        # ---------------------------------------------------------------
        interest_fact: dict | None = None
        interest_value: float | None = None
        interest_status = "MISSING"
        interest_components = ""

        l1_facts = [
            first_by_hierarchy(facts_by_tag, [tag])
            for tag in GROSS_INTEREST_L1
        ]
        l1_facts = [x for x in l1_facts if x is not None]

        if len(l1_facts) >= 2:
            vals = [float(x["value"]) for x in l1_facts]
            if not approx_equal(vals[0], vals[1], tol=1e-9):
                interest_status = "CONFLICTING"
                flags.add("INTEREST_TAGS_DISAGREE")
            else:
                interest_fact = l1_facts[0]
                interest_value = float(interest_fact["value"])
                interest_status = "PRESENT"
        elif len(l1_facts) == 1:
            interest_fact = l1_facts[0]
            interest_value = float(interest_fact["value"])
            interest_status = "PRESENT"
        else:
            l2_facts = [
                first_by_hierarchy(facts_by_tag, [tag])
                for tag in GROSS_INTEREST_L2
            ]
            l2_facts = [x for x in l2_facts if x is not None]

            if len(l2_facts) >= 2:
                vals = [float(x["value"]) for x in l2_facts]
                if not approx_equal(vals[0], vals[1], tol=1e-9):
                    interest_status = "CONFLICTING"
                    flags.add("INTEREST_TAGS_DISAGREE")
                else:
                    interest_fact = l2_facts[0]
                    interest_value = float(interest_fact["value"])
                    interest_status = "PRESENT"
            elif len(l2_facts) == 1:
                interest_fact = l2_facts[0]
                interest_value = float(interest_fact["value"])
                interest_status = "PRESENT"
                if interest_fact["tag"] == "InterestExpenseDebt":
                    flags.add("INTEREST_DEBT_ONLY")
            else:
                net_fact = first_by_hierarchy(facts_by_tag, NET_INTEREST_TAGS)
                income_fact = first_by_hierarchy(
                    facts_by_tag,
                    [INTEREST_INCOME_TAG],
                )
                paid_fact = first_by_hierarchy(
                    facts_by_tag,
                    [INTEREST_PAID_TAG],
                )

                if net_fact is not None and income_fact is not None:
                    grossed = float(income_fact["value"]) - float(net_fact["value"])
                    if grossed > 0:
                        interest_value = grossed
                        interest_fact = net_fact
                        interest_status = "PARTIAL"
                        flags.add("INTEREST_GROSSED_UP_FROM_NET")
                        interest_components = (
                            f"{income_fact['tag']}={fmt_num(income_fact['value'])};"
                            f"{net_fact['tag']}=-({fmt_num(net_fact['value'])})"
                        )

                if interest_value is None and paid_fact is not None:
                    interest_fact = paid_fact
                    interest_value = float(paid_fact["value"])
                    interest_status = "PARTIAL"
                    flags.add("INTEREST_CASH_BASIS")

                if interest_value is None and net_fact is not None:
                    flags.add("INTEREST_NET_ONLY")
                    interest_status = "MISSING"

        if interest_value is not None:
            values["interest_expense"] = fmt_num(interest_value)
            if not interest_components:
                interest_components = (
                    f"{interest_fact['tag']}={fmt_num(interest_value)}"
                )
            values["interest_expense_components"] = interest_components
            for suffix, content in provenance_values(interest_fact).items():
                values["interest_expense" + suffix] = content

        values["interest_status"] = interest_status

        # ---------------------------------------------------------------
        # Derived debt / leverage interval.
        # ---------------------------------------------------------------
        ocf = finite_number(base_row[idx["annual_operating_cash_flow"]])
        opinc = finite_number(base_row[idx["annual_operating_income"]])
        annual_equity = finite_number(base_row[idx["annual_equity"]])

        historical_cash = finite_number(base_row[idx["annual_cash"]])
        historical_cash_tag = norm_text(base_row[idx["annual_cash_tag"]])
        restricted_cash_proxy = None
        if (
            cash is None
            and historical_cash is not None
            and historical_cash_tag
            == "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
        ):
            restricted_cash_proxy = historical_cash
            flags.add("CASH_MISSING")
        elif cash is None:
            flags.add("CASH_MISSING")

        debt_found = total_debt if total_debt is not None else 0.0
        prudential_debt = debt_found
        if total_candidates:
            prudential_debt = max(v for _, v, _ in total_candidates)

        if total_debt_status == "CONFLICTING":
            flags.add("DEBT_CONFLICTING_PRUDENTIAL_VALUE")
            debt_for_lb = prudential_debt
        else:
            debt_for_lb = debt_found

        if cash is not None and total_debt is not None:
            values["net_debt"] = fmt_num(total_debt - cash)

        lb = None
        ub = None
        ub_no_cash = None

        if ocf is None:
            flags.add("OCF_MISSING")
        elif module == "BANK":
            values["net_debt_to_ocf"] = "NOT_APPLICABLE"
            flags.add("BANK_LEVERAGE_VIA_EQUITY_TO_ASSETS")
        elif ocf > 0:
            if cash is not None:
                lb = (debt_for_lb - cash) / ocf
            elif restricted_cash_proxy is not None:
                # Restricted-inclusive cash >= exact available cash, therefore
                # subtracting it produces a valid lower bound on net leverage.
                lb = (debt_for_lb - restricted_cash_proxy) / ocf

            if total_liabilities is not None:
                ub_cash = cash if cash is not None else 0.0
                ub = (total_liabilities - ub_cash) / ocf
                ub_no_cash = total_liabilities / ocf

            if lb is not None:
                values["net_debt_to_ocf_lb"] = fmt_num(lb)
            if ub is not None:
                values["net_debt_to_ocf_ub"] = fmt_num(ub)
            if ub_no_cash is not None:
                values["net_debt_to_ocf_ub_no_cash"] = fmt_num(ub_no_cash)

            if total_debt_status == "PRESENT" and cash is not None:
                exact_ratio = (total_debt - cash) / ocf
                values["net_debt_to_ocf"] = fmt_num(exact_ratio)
            elif (
                total_debt_status == "CONFLICTING"
                and cash is not None
                and total_candidates
            ):
                # R3 §7.4 / ERRATA 2: publish the prudential leverage
                # ratio from the HIGHEST debt candidate regardless of the
                # 3.0x threshold. Sector-specific ROIC rules remain separate.
                values["net_debt_to_ocf"] = fmt_num(
                    (prudential_debt - cash) / ocf
                )
            else:
                if lb is not None and lb > LEVERAGE_THRESHOLD:
                    values["net_debt_to_ocf"] = fmt_num(lb)
                    flags.add("LEVERAGE_ABOVE_THRESHOLD_BY_LOWER_BOUND")
                elif ub is not None and ub <= LEVERAGE_THRESHOLD:
                    flags.add("LEVERAGE_BELOW_THRESHOLD_BY_UPPER_BOUND")
                else:
                    flags.add("LEVERAGE_THRESHOLD_INDETERMINATE")
                    values["ios_leverage_indeterminate"] = "true"
        else:
            # OCF <= 0. With incomplete debt, 99 is safe only when a lower
            # bound already proves positive net debt.
            lower_net_debt = None
            if cash is not None:
                lower_net_debt = debt_for_lb - cash
            elif restricted_cash_proxy is not None:
                lower_net_debt = debt_for_lb - restricted_cash_proxy

            if (
                total_debt_status == "PRESENT"
                and cash is not None
                and total_debt is not None
            ):
                exact_net = total_debt - cash
                if exact_net > 0:
                    values["net_debt_to_ocf"] = "99"
                    flags.add("NET_DEBT_NOT_SERVICEABLE_FROM_OCF")
                else:
                    values["net_debt_to_ocf"] = "0"
                    flags.add("NET_CASH_NEGATIVE_OCF")
            elif (
                total_debt_status == "CONFLICTING"
                and cash is not None
                and total_candidates
            ):
                # R3 §7.4 / ERRATA 2: for non-positive OCF, preserve the
                # same prudential highest-candidate convention.
                if prudential_debt - cash > 0:
                    values["net_debt_to_ocf"] = "99"
                    flags.add("NET_DEBT_NOT_SERVICEABLE_FROM_OCF")
                else:
                    values["net_debt_to_ocf"] = "0"
                    flags.add("NET_CASH_NEGATIVE_OCF")
            elif lower_net_debt is not None and lower_net_debt > 0:
                values["net_debt_to_ocf"] = "99"
                flags.add("NET_DEBT_NOT_SERVICEABLE_FROM_OCF")
                flags.add("LEVERAGE_ABOVE_THRESHOLD_BY_LOWER_BOUND")
            else:
                flags.add("LEVERAGE_THRESHOLD_INDETERMINATE")
                values["ios_leverage_indeterminate"] = "true"

        # ---------------------------------------------------------------
        # Interest coverage.
        # ---------------------------------------------------------------
        if module == "BANK":
            values["interest_coverage"] = "NOT_APPLICABLE"
            flags.add("BANK_INTEREST_IS_FUNDING_COST")
        elif interest_status == "CONFLICTING":
            values["interest_coverage"] = "CONFLICTING"
        elif interest_value is not None:
            if interest_value == 0 and debt_found > 0:
                values["interest_coverage"] = "CONFLICTING"
                values["interest_status"] = "CONFLICTING"
                interest_status = "CONFLICTING"
                flags.add("ZERO_INTEREST_WITH_DEBT")
            elif interest_value > 0 and opinc is not None:
                coverage = opinc / interest_value
                values["interest_coverage"] = fmt_num(coverage)
                if opinc <= 0:
                    flags.add("EBIT_NON_POSITIVE")
        elif debt_found > 0:
            flags.add("INTEREST_MISSING_WITH_DEBT")

        # ---------------------------------------------------------------
        # ROIC.
        # ---------------------------------------------------------------
        if module in {"BANK", "INSURANCE"}:
            values["roic"] = "NOT_APPLICABLE"
        elif total_debt_status == "CONFLICTING":
            # Safe in lin(); required by §7.4.
            values["roic"] = "CONFLICTING"
        elif total_debt_status == "PARTIAL":
            flags.add("ROIC_DEBT_PARTIAL")
        elif (
            total_debt_status == "PRESENT"
            and total_debt is not None
            and cash is not None
            and annual_equity is not None
            and opinc is not None
        ):
            invested_capital = annual_equity + total_debt - cash
            values["invested_capital"] = fmt_num(invested_capital)
            if invested_capital <= 0:
                flags.add("INVESTED_CAPITAL_NON_POSITIVE")
            else:
                values["roic"] = fmt_num(
                    opinc * (1.0 - 0.21) / invested_capital
                )

        # If the exact invested-capital denominator cannot be trusted, leave it
        # blank rather than silently publishing a PARTIAL denominator.
        if total_debt_status != "PRESENT":
            values["invested_capital"] = ""

        # BR-04 overall status.
        if total_debt_status == "CONFLICTING" or interest_status == "CONFLICTING":
            br04_status = "CONFLICTING"
        elif total_debt_status == "MISSING" and interest_status == "MISSING":
            br04_status = "MISSING"
        elif (
            total_debt_status == "PRESENT"
            and interest_status == "PRESENT"
        ):
            br04_status = "PRESENT"
        else:
            br04_status = "PARTIAL"

        values["br04_status"] = br04_status
        values["br04_flags"] = ";".join(sorted(flags))

        state_counts[br04_status] += 1
        for flag in flags:
            flag_counts[flag] += 1

        # Components evidence: only facts actually selected into BR-04 values.
        used_as_map: list[tuple[str, list[dict]]] = [
            ("current_debt", current_used),
            ("long_term_debt", noncurrent_used),
            ("finance_lease_liabilities", finance_items),
            ("total_debt", total_used),
            ("operating_lease_liabilities", op_lease_items),
        ]
        if cash_fact:
            used_as_map.append(("cash_and_equivalents", [cash_fact]))
        if sti_fact:
            used_as_map.append(("short_term_investments", [sti_fact]))
        if lse_fact:
            used_as_map.append(("total_liabilities_and_equity", [lse_fact]))
        if liab_fact:
            used_as_map.append(("total_liabilities", [liab_fact]))
        if interest_fact:
            used_as_map.append(("interest_expense", [interest_fact]))

        seen_component_keys: set[tuple] = set()
        for used_as, used_items in used_as_map:
            for item in used_items:
                key = (
                    ticker,
                    item.get("adsh"),
                    item.get("stmt"),
                    item.get("line"),
                    item.get("tag"),
                    used_as,
                )
                if key in seen_component_keys:
                    continue
                seen_component_keys.add(key)
                components_out.append(
                    {
                        "ticker": ticker,
                        "adsh": item.get("adsh", ""),
                        "stmt": item.get("stmt", ""),
                        "line": item.get("line", ""),
                        "plabel": item.get("plabel", ""),
                        "tag": item.get("tag", ""),
                        "version": item.get("version", ""),
                        "class": item.get("class", ""),
                        "value": fmt_num(item.get("value")),
                        "ddate": item.get("ddate", ""),
                        "qtrs": item.get("qtrs", ""),
                        "uom": item.get("uom", ""),
                        "used_as": used_as,
                    }
                )

        if values["ios_leverage_indeterminate"] == "true":
            indeterminate_out.append(
                {
                    "ticker": ticker,
                    "adsh": adsh,
                    "total_debt_status": total_debt_status,
                    "lb": values["net_debt_to_ocf_lb"],
                    "ub": values["net_debt_to_ocf_ub"],
                    "cash_present": cash is not None,
                    "ocf_present": ocf is not None,
                    "flags": values["br04_flags"],
                }
            )

        result_by_ticker[ticker] = values

    # -----------------------------------------------------------------------
    # Candidate creation: preserve the original 212-column text verbatim and
    # append only new BR-04 fields.
    # -----------------------------------------------------------------------
    new_header = header + BR04_COLUMNS
    with CANDIDATE_PATH.open("w", encoding="utf-8", newline="\n") as out:
        out.write(physical_header := csv_fragment(new_header))
        out.write("\n")
        for raw_line, parsed in zip(raw_rows, parsed_rows):
            ticker = norm_text(parsed[idx["ticker"]])
            br04 = result_by_ticker[ticker]
            fragment = csv_fragment([br04.get(col, "") for col in BR04_COLUMNS])
            out.write(raw_line)
            out.write(",")
            out.write(fragment)
            out.write("\n")

    candidate_sha = sha256_file(CANDIDATE_PATH)

    # Verify old columns string-by-string immediately in S1. This is not the
    # formal T19 report (S2), but S1 refuses to create a knowingly altered base.
    with CANDIDATE_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        cand_header = next(reader)
        candidate_rows = list(reader)

    if cand_header[: len(header)] != header:
        raise SystemExit("S1_BLOCK: header base alterato nel candidato")
    if len(candidate_rows) != len(parsed_rows):
        raise SystemExit("S1_BLOCK: numero righe candidato diverso dalla base")

    old_cells_changed = 0
    for base, cand in zip(parsed_rows, candidate_rows):
        if cand[: len(header)] != base:
            old_cells_changed += sum(
                a != b for a, b in zip(base, cand[: len(header)])
            )

    if old_cells_changed:
        raise SystemExit(
            f"S1_BLOCK: {old_cells_changed} celle pre-BR04 cambiate"
        )

    # Base must still be unchanged after the long SEC download/build.
    end_base_sha = sha256_file(FUNDAMENTALS_PATH)
    if end_base_sha != base_sha:
        raise SystemExit(
            "S1_BLOCK_BASE_CHANGED: data/current è cambiato durante S1. "
            "Scartare il candidato e rieseguire T00-bis."
        )

    # Evidence / audit files.
    write_components(components_out)
    write_custom_audit(all_custom_audit)

    with INDETERMINATE_PATH.open("w", encoding="utf-8", newline="") as f:
        cols = [
            "ticker",
            "adsh",
            "total_debt_status",
            "lb",
            "ub",
            "cash_present",
            "ocf_present",
            "flags",
        ]
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(indeterminate_out)

    diff_report = {
        "schema": "br04_diff_vs_current_s1_v1.0",
        "generated_at_utc": now_iso(),
        "run_id": RUN_ID,
        "base_canonical_sha256": base_sha,
        "candidate_sha256": candidate_sha,
        "rows_base": len(parsed_rows),
        "rows_candidate": len(candidate_rows),
        "base_columns": len(header),
        "candidate_columns": len(cand_header),
        "new_br04_columns": len(BR04_COLUMNS),
        "existing_cells_changed": old_cells_changed,
        "existing_columns_string_equal": old_cells_changed == 0,
    }
    bridge.write_json_atomic(DIFF_PATH, diff_report)

    build_report = {
        "schema": "br04_s1_build_v1.0",
        "generated_at_utc": now_iso(),
        "run_id": RUN_ID,
        "phase": "S1",
        "implementation_revision": "br04_s1_builder_r3",
        "base_canonical_sha256": base_sha,
        "candidate_sha256": candidate_sha,
        "source_t00bis_run_id": source_t00_run_id,
        "source_t00bis_schema": t00.get("schema"),
        "universe_rows": len(parsed_rows),
        "base_columns": len(header),
        "candidate_columns": len(cand_header),
        "br04_columns_added": len(BR04_COLUMNS),
        "sec_quarters": [q.key for q in selected_quarters],
        "sec_index": sec_index_meta,
        "closure_supported": CLOSURE_SUPPORTED,
        "closure_policy": (
            "No §7.2 closure fabricated from PRE; found debt remains PARTIAL "
            "and absent debt remains MISSING."
        ),
        "module_counts": dict(sorted(module_counts.items())),
        "br04_status_counts": dict(sorted(state_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "components_rows": len(components_out),
        "custom_audit_rows": len(all_custom_audit),
        "leverage_indeterminate_rows": len(indeterminate_out),
        "canonical_modified": False,
        "s2_regression_executed": False,
        "s3_transport_executed": False,
        "s4_engine_executed": False,
        "blind_test_executed": False,
    }
    bridge.write_json_atomic(BUILD_REPORT_PATH, build_report)

    # Candidate manifest/status are staging-only. They are not promoted here.
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        manifest = {}

    manifest["schema_version"] = "1.4"
    manifest["br04_debt_interest"] = {
        "schema": SCHEMA,
        "phase": "S1_CANDIDATE",
        "generated_at_utc": now_iso(),
        "base_canonical_sha256": base_sha,
        "candidate_sha256": candidate_sha,
        "source_t00bis_run_id": source_t00_run_id,
        "latest_available_quarter": selected_quarters[-1].key,
        "closure_supported_by_current_fsds": False,
        "candidate_path": str(CANDIDATE_PATH.relative_to(ROOT)),
        "canonical_modified": False,
        "invariant": "`MISSING` resta `MISSING`: nessuna assenza è convertita in zero",
    }
    bridge.write_json_atomic(MANIFEST_CANDIDATE_PATH, manifest)

    base_status = (
        STATUS_PATH.read_text(encoding="utf-8")
        if STATUS_PATH.exists()
        else "# Investment OS Data Bridge — stato\n"
    )
    status_section = f"""

## V4.1 enrichment BR-04 — S1 CANDIDATE ONLY

- Run ID: **{RUN_ID}**
- Base canonical SHA-256: `{base_sha}`
- Candidate SHA-256: `{candidate_sha}`
- Source T00-bis run: **{source_t00_run_id}**
- Candidate rows: **{len(parsed_rows)}**
- Base columns preserved string-for-string: **YES**
- BR-04 columns appended: **{len(BR04_COLUMNS)}**
- Strict BS closure from current SEC FSDS: **NOT DEMONSTRABLE**
- Leverage-threshold indeterminate rows: **{len(indeterminate_out)}**
- `data/current/` modified: **NO**
- S2 regression: **NOT YET EXECUTED**
- S3 transport: **NOT YET EXECUTED**
- S4 engine test: **NOT YET EXECUTED**
- Blind Test: **NOT EXECUTED**

**`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.**

This file is staging evidence only and must not be treated as canonical until
S2, S3, S4, human approval, T31 and atomic promotion have all succeeded.
"""
    STATUS_CANDIDATE_PATH.write_text(
        base_status.rstrip() + status_section,
        encoding="utf-8",
    )

    print("OK — BR04 S1 candidate costruito.")
    print(f"base_canonical_sha256={base_sha}")
    print(f"candidate_sha256={candidate_sha}")
    print(f"candidate={CANDIDATE_PATH.relative_to(ROOT)}")
    print(f"existing_cells_changed={old_cells_changed}")
    print("data/current modified: NO")
    print("S2/S3/S4/Blind Test: NOT EXECUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
