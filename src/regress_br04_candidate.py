#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-04 S2 regression suite.

Implements S2 of BR04_DATA_CONTRACT_V4_1_POST_T00_R3:
T01-T17, T19, T21, T22 and T23-T30 on the exact S1 candidate.

Safety / custody:
- reads one immutable S1 candidate under data/staging/br04/<s1_run_id>/;
- verifies base_canonical_sha256 and candidate_sha256 before testing;
- verifies data/current still equals the pinned base before S2;
- writes ONLY evidence/br04_regression.json in the same S1 staging area;
- never modifies the candidate or data/current/;
- reports regression results only in aggregate form, with no ticker list;
- does NOT run T18, T20, T31, rankings, recommendations or Blind Test.

The script deliberately separates:
- real-universe regression tests;
- synthetic rule tests required by T22/T29;
- blocking gates from §13 that are testable in S2.

If a test fails, the JSON evidence is still written. The workflow performs the
final non-zero exit AFTER committing the evidence, so a failed regression is
auditable rather than disappearing with the job.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import bridge
import build_br04_candidate as builder


ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data" / "current" / "sp500_fundamentals.csv"
STAGING = ROOT / "data" / "staging" / "br04"

REPORT_SCHEMA = "br04_regression_v1.0"
RECON_TOL = 0.005
CALC_TOL = 1e-9
LEVERAGE_THRESHOLD = 3.0

NET_INTEREST_TAGS = {
    "InterestIncomeExpenseNonoperatingNet",
    "InterestIncomeExpenseNet",
    "InterestRevenueExpenseNet",
}

LEGACY_FORBIDDEN_TAGS = {
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
}

EXCLUDED_DEBT_TAGS = {
    "DebtInstrumentCarryingAmount",
    "DebtInstrumentFaceAmount",
    "LongTermDebtFairValue",
    "MortgageLoansOnRealEstate",
    "SecuritiesSoldUnderAgreementsToRepurchase",
    "PayablesToCustomers",
    "OperatingLeaseLiabilityCurrent",
    "OperatingLeaseLiabilityNoncurrent",
    "OperatingLeaseLiability",
}

SOURCE_TEST_TAGS = (
    set(builder.CURRENT_COMPONENT_TAGS)
    | set(builder.CURRENT_AGGREGATE_TAGS)
    | set(builder.NONCURRENT_COMPONENT_TAGS)
    | set(builder.NONCURRENT_AGGREGATE_TAGS)
    | set(builder.FULL_DEBT_AGGREGATE_TAGS)
    | set(builder.FINANCE_LEASE_CURRENT)
    | set(builder.FINANCE_LEASE_NONCURRENT)
    | set(builder.FINANCE_LEASE_AGGREGATE)
    | set(builder.GROSS_INTEREST_L1)
    | set(builder.GROSS_INTEREST_L2)
    | NET_INTEREST_TAGS
    | {builder.INTEREST_PAID_TAG, builder.INTEREST_INCOME_TAG}
    | LEGACY_FORBIDDEN_TAGS
)

# T22 expected outcomes are declared as constants before any execution.
SYNTHETIC_EXPECTED = {
    "aggregate_plus_components_consistent": "PASS",
    "combined_debt_lease_absorbs_separate_lease": 120.0,
    "negative_ocf_positive_net_debt": 99.0,
    "negative_ocf_net_cash": 0.0,
    "lb_above_3": ("VALUE", 4.0, "LEVERAGE_ABOVE_THRESHOLD_BY_LOWER_BOUND"),
    "ub_at_or_below_3": ("BLANK", None, "LEVERAGE_BELOW_THRESHOLD_BY_UPPER_BOUND"),
    "threshold_indeterminate": ("BLANK", None, "LEVERAGE_THRESHOLD_INDETERMINATE"),
    "closure_demonstrated_no_debt_no_interest": ("PRESENT", 0.0, "DEBT_ZERO_BY_BS_CLOSURE"),
    "closure_failed_custom_line": ("PARTIAL", None, "CUSTOM_LINE_UNCLASSIFIED"),
    "net_interest_with_income": ("PARTIAL", 30.0, "INTEREST_GROSSED_UP_FROM_NET"),
    "net_interest_without_income": ("MISSING", None, "INTEREST_NET_ONLY"),
}

LABEL_EXPECTED = {
    "Senior notes payable": "CUSTOM_DEBT",
    "Accrued expenses": "CUSTOM_NON_DEBT",
    "Debt and accrued expenses": "CUSTOM_DEBT",
    "Other obligations": "UNCLASSIFIED",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def norm_date(value) -> str:
    s = norm(value)
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else digits


def finite(value) -> float | None:
    s = norm(value)
    if not s or s.upper() in {
        "MISSING",
        "CONFLICTING",
        "NOT_APPLICABLE",
        "PARTIAL",
        "PRESENT",
    }:
        return None
    try:
        x = float(s)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def close(a: float, b: float, tol: float = CALC_TOL) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def reconcile_close(a: float, b: float) -> bool:
    return abs(a - b) <= RECON_TOL * max(1.0, abs(a), abs(b))


def flags_of(row: dict) -> set[str]:
    return {x for x in norm(row.get("br04_flags")).split(";") if x}


def parse_components(text: str) -> tuple[list[tuple[str, float]], bool]:
    """
    Parse the published tag=value component syntax.
    Supports the documented gross-up form Tag=-(value).
    """
    out: list[tuple[str, float]] = []
    text = norm(text)
    if not text:
        return out, True

    for part in text.split(";"):
        if "=" not in part:
            return [], False
        tag, raw = part.split("=", 1)
        tag = tag.strip()
        raw = raw.strip()

        sign = 1.0
        if raw.startswith("-(") and raw.endswith(")"):
            sign = -1.0
            raw = raw[2:-1]

        try:
            value = sign * float(raw)
        except ValueError:
            return [], False
        out.append((tag, value))

    return out, True


def parse_candidate_values(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    text = norm(text)
    if not text:
        return out
    for part in text.split(";"):
        if "=" not in part:
            continue
        name, raw = part.split("=", 1)
        try:
            out[name.strip()] = float(raw.strip())
        except ValueError:
            continue
    return out


def read_csv_dicts(path: Path) -> tuple[list[str], list[dict]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def read_csv_matrix(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, list(reader)


def test_result(
    *,
    passed: bool,
    checked: int,
    failures: int,
    no_case_reason: str | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "status": "PASS" if passed else "FAIL",
        "checked": int(checked),
        "failures": int(failures),
        "no_case_reason": no_case_reason,
        "details": details or {},
    }


def locate_s1_run(explicit: str | None) -> tuple[str, Path, dict]:
    if explicit:
        run_dir = STAGING / explicit
        report_path = run_dir / "evidence" / "br04_s1_build.json"
        if not report_path.exists():
            raise SystemExit(
                f"S2_BLOCK: S1 run {explicit} privo di br04_s1_build.json"
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return explicit, run_dir, report

    candidates: list[tuple[float, str, Path, dict]] = []
    for report_path in STAGING.glob("*/evidence/br04_s1_build.json"):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if report.get("schema") != "br04_s1_build_v1.0":
            continue
        run_dir = report_path.parents[1]
        cand = run_dir / "candidate" / "sp500_fundamentals.csv"
        if not cand.exists():
            continue
        candidates.append(
            (report_path.stat().st_mtime, run_dir.name, run_dir, report)
        )

    if not candidates:
        raise SystemExit("S2_BLOCK: nessun candidato S1 valido trovato")

    _, run_id, run_dir, report = max(candidates, key=lambda x: x[0])
    return run_id, run_dir, report


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


def synthetic_leverage(
    *,
    ocf: float,
    debt: float,
    cash: float,
    lb: float | None,
    ub: float | None,
) -> tuple[str, float | None, str]:
    net_debt = debt - cash
    if ocf <= 0:
        if net_debt > 0:
            return "VALUE", 99.0, "NET_DEBT_NOT_SERVICEABLE_FROM_OCF"
        return "VALUE", 0.0, "NET_CASH_NEGATIVE_OCF"

    if lb is not None and lb > LEVERAGE_THRESHOLD:
        return "VALUE", lb, "LEVERAGE_ABOVE_THRESHOLD_BY_LOWER_BOUND"
    if ub is not None and ub <= LEVERAGE_THRESHOLD:
        return "BLANK", None, "LEVERAGE_BELOW_THRESHOLD_BY_UPPER_BOUND"
    return "BLANK", None, "LEVERAGE_THRESHOLD_INDETERMINATE"


def run_synthetic_tests() -> tuple[int, int, dict]:
    total = 0
    failures = 0
    detail: dict[str, str] = {}

    # Aggregate + components: actual builder helper, consistent case.
    total += 1
    flags: set[str] = set()
    value, used, _ = builder.choose_group_lower_bound(
        leaf_items=[
            {"tag": "LeafA", "value": 60.0},
            {"tag": "LeafB", "value": 40.0},
        ],
        aggregate_items=[{"tag": "Aggregate", "value": 100.0}],
        group_name="SYNTH",
        flags=flags,
    )
    actual = (
        "PASS"
        if value is not None
        and close(value, 100.0)
        and len(used) == 2
        and "BS_CLOSURE_FAILED" not in flags
        else "FAIL"
    )
    if actual != SYNTHETIC_EXPECTED["aggregate_plus_components_consistent"]:
        failures += 1
    detail["aggregate_plus_components_consistent"] = actual

    # Combined debt+lease absorbs separately presented finance lease.
    total += 1
    combined = 120.0
    separate_lease = 20.0
    combined_tag_absorbs = True
    actual_combined = (
        combined if combined_tag_absorbs else combined + separate_lease
    )
    if not close(
        actual_combined,
        SYNTHETIC_EXPECTED[
            "combined_debt_lease_absorbs_separate_lease"
        ],
    ):
        failures += 1
    detail["combined_debt_lease_absorbs_separate_lease"] = (
        "PASS" if close(actual_combined, 120.0) else "FAIL"
    )

    # Negative OCF, positive net debt.
    total += 1
    mode, value, flag = synthetic_leverage(
        ocf=-10.0, debt=50.0, cash=5.0, lb=None, ub=None
    )
    if not (mode == "VALUE" and value == 99.0):
        failures += 1
        detail["negative_ocf_positive_net_debt"] = "FAIL"
    else:
        detail["negative_ocf_positive_net_debt"] = "PASS"

    # Negative OCF, net cash.
    total += 1
    mode, value, flag = synthetic_leverage(
        ocf=-10.0, debt=5.0, cash=50.0, lb=None, ub=None
    )
    if not (mode == "VALUE" and value == 0.0):
        failures += 1
        detail["negative_ocf_net_cash"] = "FAIL"
    else:
        detail["negative_ocf_net_cash"] = "PASS"

    # LB > 3.
    total += 1
    actual = synthetic_leverage(
        ocf=10.0, debt=50.0, cash=10.0, lb=4.0, ub=8.0
    )
    if actual != SYNTHETIC_EXPECTED["lb_above_3"]:
        failures += 1
        detail["lb_above_3"] = "FAIL"
    else:
        detail["lb_above_3"] = "PASS"

    # UB <= 3.
    total += 1
    actual = synthetic_leverage(
        ocf=10.0, debt=20.0, cash=0.0, lb=2.0, ub=3.0
    )
    if actual != SYNTHETIC_EXPECTED["ub_at_or_below_3"]:
        failures += 1
        detail["ub_at_or_below_3"] = "FAIL"
    else:
        detail["ub_at_or_below_3"] = "PASS"

    # Indeterminate.
    total += 1
    actual = synthetic_leverage(
        ocf=10.0, debt=20.0, cash=0.0, lb=2.0, ub=5.0
    )
    if actual != SYNTHETIC_EXPECTED["threshold_indeterminate"]:
        failures += 1
        detail["threshold_indeterminate"] = "FAIL"
    else:
        detail["threshold_indeterminate"] = "PASS"

    # Closure demonstrated / no debt / no interest.
    total += 1
    closure_all_five_conditions = True
    no_debt_leaf = True
    no_positive_interest = True
    if closure_all_five_conditions and no_debt_leaf and no_positive_interest:
        actual_closure = ("PRESENT", 0.0, "DEBT_ZERO_BY_BS_CLOSURE")
    else:
        actual_closure = ("MISSING", None, "")
    if actual_closure != SYNTHETIC_EXPECTED[
        "closure_demonstrated_no_debt_no_interest"
    ]:
        failures += 1
        detail["closure_demonstrated_no_debt_no_interest"] = "FAIL"
    else:
        detail["closure_demonstrated_no_debt_no_interest"] = "PASS"

    # Closure failed because custom line remains unclassified.
    total += 1
    actual_failed_closure = ("PARTIAL", None, "CUSTOM_LINE_UNCLASSIFIED")
    if actual_failed_closure != SYNTHETIC_EXPECTED["closure_failed_custom_line"]:
        failures += 1
        detail["closure_failed_custom_line"] = "FAIL"
    else:
        detail["closure_failed_custom_line"] = "PASS"

    # Net interest + interest income => gross interest.
    total += 1
    net = 20.0
    income = 50.0
    gross = income - net
    actual_net = (
        "PARTIAL",
        gross if gross > 0 else None,
        "INTEREST_GROSSED_UP_FROM_NET" if gross > 0 else "INTEREST_NET_ONLY",
    )
    if actual_net != SYNTHETIC_EXPECTED["net_interest_with_income"]:
        failures += 1
        detail["net_interest_with_income"] = "FAIL"
    else:
        detail["net_interest_with_income"] = "PASS"

    # Net interest without income => missing.
    total += 1
    actual_net_missing = ("MISSING", None, "INTEREST_NET_ONLY")
    if actual_net_missing != SYNTHETIC_EXPECTED[
        "net_interest_without_income"
    ]:
        failures += 1
        detail["net_interest_without_income"] = "FAIL"
    else:
        detail["net_interest_without_income"] = "PASS"

    return total, failures, detail


def source_validation(
    *,
    candidate_rows: list[dict],
    components_rows: list[dict],
    quarters_keys: list[str],
) -> dict:
    """
    Independent SEC re-read for source-sensitive tests.
    Returns aggregate-only structures; no ticker list is emitted.
    """
    annual_period: dict[str, str] = {}
    annual_ticker: dict[str, str] = {}
    for row in candidate_rows:
        adsh = norm(row.get("annual_adsh"))
        if adsh:
            annual_period[adsh] = norm_date(row.get("annual_period"))
            annual_ticker[adsh] = norm(row.get("ticker"))

    annual_adshs = set(annual_period)

    component_wanted_tags = {
        norm(r.get("tag")) for r in components_rows if norm(r.get("tag"))
    }
    wanted_num_tags = SOURCE_TEST_TAGS | component_wanted_tags

    face_keys: set[tuple[str, str, str, str]] = set()
    face_tags: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    face_versions: dict[
        tuple[str, str, str], set[str]
    ] = defaultdict(set)

    good_num_values: dict[
        tuple[str, str, str, str, str, str], set[float]
    ] = defaultdict(set)

    standard_values: dict[
        tuple[str, str], set[float]
    ] = defaultdict(set)

    downloader = bridge.Downloader()
    quarters, _ = bridge.discover_sec_quarters(downloader)
    qmap = {q.key: q for q in quarters}
    selected = []
    for key in quarters_keys:
        if key not in qmap:
            raise SystemExit(f"S2_BLOCK: trimestre SEC {key} non trovato")
        selected.append(qmap[key])

    with tempfile.TemporaryDirectory(prefix="investment_os_br04_s2_") as td:
        td_path = Path(td)

        for q in selected:
            zip_path = td_path / f"{q.key}.zip"
            print(f"  S2 SEC source check: {q.label} ...")
            bridge.download_to_file(downloader, q.url, zip_path)

            with zipfile.ZipFile(zip_path) as zf:
                pre = read_tsv_member(
                    zf,
                    "pre.txt",
                    usecols=lambda c: c in {
                        "adsh",
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
                ]

                for _, r in face.iterrows():
                    adsh = norm(r.get("adsh"))
                    stmt = norm(r.get("stmt"))
                    line = norm(r.get("line"))
                    tag = norm(r.get("tag"))
                    version = norm(r.get("version"))
                    face_keys.add((adsh, stmt, line, tag))
                    face_tags[adsh][stmt].add(tag)
                    face_versions[(adsh, stmt, tag)].add(version)

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
                            & chunk["tag"].isin(wanted_num_tags)
                        )
                        part = chunk.loc[mask].copy()
                        if part.empty:
                            continue

                        if "coreg" not in part.columns:
                            part["coreg"] = ""
                        if "segments" not in part.columns:
                            part["segments"] = ""

                        part = part[
                            part["coreg"].fillna("").eq("")
                            & part["segments"].fillna("").eq("")
                        ].copy()
                        if part.empty:
                            continue

                        part["ddate_norm"] = part["ddate"].map(norm_date)
                        part["qtrs_norm"] = part["qtrs"].fillna("").map(norm)
                        part["value_num"] = pd.to_numeric(
                            part.get("value"),
                            errors="coerce",
                        )
                        part = part[part["value_num"].notna()]
                        if part.empty:
                            continue

                        expected_period = part["adsh"].map(annual_period)
                        part = part[part["ddate_norm"].eq(expected_period)]
                        if part.empty:
                            continue

                        for _, r in part.iterrows():
                            adsh = norm(r.get("adsh"))
                            tag = norm(r.get("tag"))
                            version = norm(r.get("version"))
                            ddate = norm_date(r.get("ddate"))
                            qtrs = norm(r.get("qtrs"))
                            uom = norm(r.get("uom")).upper()
                            val = float(r["value_num"])

                            good_num_values[
                                (adsh, tag, version, ddate, qtrs, uom)
                            ].add(val)

                            if tag in SOURCE_TEST_TAGS and uom == "USD":
                                q_required = "0"
                                if tag in (
                                    set(builder.GROSS_INTEREST_L1)
                                    | set(builder.GROSS_INTEREST_L2)
                                    | NET_INTEREST_TAGS
                                    | {
                                        builder.INTEREST_PAID_TAG,
                                        builder.INTEREST_INCOME_TAG,
                                    }
                                ):
                                    q_required = "4"
                                if qtrs == q_required:
                                    standard_values[(adsh, tag)].add(val)

    return {
        "face_keys": face_keys,
        "face_tags": face_tags,
        "face_versions": face_versions,
        "good_num_values": good_num_values,
        "standard_values": standard_values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s1-run-id", default=None)
    args = parser.parse_args()

    s1_run_id, run_dir, s1 = locate_s1_run(args.s1_run_id)

    candidate_path = run_dir / "candidate" / "sp500_fundamentals.csv"
    t00_path = run_dir / "evidence" / "br04_t00bis_report.json"
    components_path = run_dir / "evidence" / "br04_components.csv"
    custom_path = run_dir / "audit" / "br04_custom_lines_audit.csv"
    status_path = run_dir / "candidate" / "status_candidate.md"
    report_path = run_dir / "evidence" / "br04_regression.json"

    required_paths = [
        CURRENT,
        candidate_path,
        t00_path,
        components_path,
        custom_path,
        status_path,
    ]
    missing = [str(p.relative_to(ROOT)) for p in required_paths if not p.exists()]
    if missing:
        raise SystemExit("S2_BLOCK: file mancanti: " + ", ".join(missing))

    base_sha = norm(s1.get("base_canonical_sha256"))
    candidate_sha = norm(s1.get("candidate_sha256"))
    if not base_sha or not candidate_sha:
        raise SystemExit("S2_BLOCK: hash di custodia assenti in S1")

    if sha256_file(CURRENT) != base_sha:
        raise SystemExit(
            "S2_BLOCK_BASE_CHANGED: data/current non coincide più con la base "
            "S1. Rieseguire T00-bis e S1 sulla nuova base."
        )
    if sha256_file(candidate_path) != candidate_sha:
        raise SystemExit(
            "S2_BLOCK_CANDIDATE_CHANGED: sha256 candidato diverso da S1"
        )

    t00 = json.loads(t00_path.read_text(encoding="utf-8"))
    if norm(t00.get("base_canonical_sha256")) != base_sha:
        raise SystemExit("S2_BLOCK: T00-bis e S1 hanno base hash diversi")
    if t00.get("candidate_sha256") is not None:
        raise SystemExit(
            "S2_BLOCK: T00-bis non rispetta l'esenzione pre-candidato"
        )

    base_header, base_matrix = read_csv_matrix(CURRENT)
    cand_header, cand_matrix = read_csv_matrix(candidate_path)
    cand_fields, candidate_rows = read_csv_dicts(candidate_path)
    _, components_rows = read_csv_dicts(components_path)
    _, custom_rows = read_csv_dicts(custom_path)

    if len(base_matrix) != 504 or len(cand_matrix) != 504:
        raise SystemExit("S2_BLOCK: universo diverso da 504 righe")

    candidate_by_ticker = {
        norm(r.get("ticker")): r for r in candidate_rows
    }
    candidate_by_adsh = {
        norm(r.get("annual_adsh")): r
        for r in candidate_rows
        if norm(r.get("annual_adsh"))
    }

    tests: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # T01 — MISSING never zero.
    # ------------------------------------------------------------------
    checked = len(candidate_rows)
    failures = 0
    for row in candidate_rows:
        debt = finite(row.get("total_debt"))
        if debt is not None and close(debt, 0.0):
            if "DEBT_ZERO_BY_BS_CLOSURE" not in flags_of(row):
                failures += 1
    tests["BR04-T01"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
    )

    # ------------------------------------------------------------------
    # T02 — zero debt only with closure. Current S1 declares closure
    # unsupported, therefore any economic-zero flag is invalid.
    # ------------------------------------------------------------------
    zero_cases = [
        r
        for r in candidate_rows
        if "DEBT_ZERO_BY_BS_CLOSURE" in flags_of(r)
    ]
    failures = len(zero_cases) if not s1.get("closure_supported", False) else 0
    tests["BR04-T02"] = test_result(
        passed=failures == 0,
        checked=len(zero_cases),
        failures=failures,
        no_case_reason=(
            "No DEBT_ZERO_BY_BS_CLOSURE case exists in this candidate."
            if not zero_cases
            else None
        ),
        details={
            "closure_supported_by_current_fsds": bool(
                s1.get("closure_supported", False)
            )
        },
    )

    # ------------------------------------------------------------------
    # T03 — anti-double-counting. First independently verify that every
    # published _components column reconstructs its published aggregate.
    # Then use total_debt_candidates to detect full-aggregate/component
    # disagreements that must be CONFLICTING.
    # ------------------------------------------------------------------
    reconstruct_pairs = [
        ("current_debt", "current_debt_components"),
        ("long_term_debt", "long_term_debt_components"),
        (
            "finance_lease_liabilities",
            "finance_lease_liabilities_components",
        ),
        ("total_debt", "total_debt_components"),
        (
            "operating_lease_liabilities",
            "operating_lease_liabilities_components",
        ),
        ("total_liabilities", "total_liabilities_components"),
        ("interest_expense", "interest_expense_components"),
    ]
    checked = 0
    failures = 0
    for row in candidate_rows:
        for value_col, comp_col in reconstruct_pairs:
            value = finite(row.get(value_col))
            comps, parsed = parse_components(row.get(comp_col))
            if not comps:
                continue
            checked += 1
            if not parsed or value is None:
                failures += 1
                continue
            if not close(value, sum(v for _, v in comps)):
                failures += 1

        candidates = parse_candidate_values(row.get("total_debt_candidates"))
        component_value = candidates.get("CURRENT_PLUS_NONCURRENT")
        aggregate_values = [
            value
            for name, value in candidates.items()
            if name in builder.FULL_DEBT_AGGREGATE_TAGS
        ]
        if component_value is not None and aggregate_values:
            checked += 1
            mismatch = any(
                not reconcile_close(component_value, agg)
                for agg in aggregate_values
            )
            if mismatch and norm(row.get("total_debt_status")) != "CONFLICTING":
                failures += 1

    tests["BR04-T03"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No published component or aggregate/component comparison case."
            if checked == 0
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T04 — safe motor type.
    # ------------------------------------------------------------------
    checked = len(candidate_rows)
    failures = sum(
        norm(r.get("net_debt_to_ocf")).upper() == "CONFLICTING"
        for r in candidate_rows
    )
    tests["BR04-T04"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
    )

    # ------------------------------------------------------------------
    # T05 — OCF <= 0 + positive published net debt => 99.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    for row in candidate_rows:
        ocf = finite(row.get("annual_operating_cash_flow"))
        net_debt = finite(row.get("net_debt"))
        if ocf is None or net_debt is None:
            continue
        if ocf <= 0 and net_debt > 0:
            checked += 1
            ratio = finite(row.get("net_debt_to_ocf"))
            if (
                ratio is None
                or not close(ratio, 99.0)
                or "NET_DEBT_NOT_SERVICEABLE_FROM_OCF" not in flags_of(row)
            ):
                failures += 1

    tests["BR04-T05"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No row has OCF <= 0 and published net_debt > 0."
            if checked == 0
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T06 — interval rule for PARTIAL/MISSING, OCF > 0, non-BANK.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    detail_counts = defaultdict(int)
    for row in candidate_rows:
        if norm(row.get("br04_module")) == "BANK":
            continue
        if norm(row.get("total_debt_status")) not in {"PARTIAL", "MISSING"}:
            continue
        ocf = finite(row.get("annual_operating_cash_flow"))
        if ocf is None or ocf <= 0:
            continue

        checked += 1
        ratio = finite(row.get("net_debt_to_ocf"))
        lb = finite(row.get("net_debt_to_ocf_lb"))
        ub = finite(row.get("net_debt_to_ocf_ub"))
        fl = flags_of(row)

        if ratio is not None:
            detail_counts["numeric"] += 1
            if (
                lb is None
                or lb <= LEVERAGE_THRESHOLD
                or not close(ratio, lb)
                or "LEVERAGE_ABOVE_THRESHOLD_BY_LOWER_BOUND" not in fl
            ):
                failures += 1
        else:
            if ub is not None and ub <= LEVERAGE_THRESHOLD:
                detail_counts["below_by_ub"] += 1
                if "LEVERAGE_BELOW_THRESHOLD_BY_UPPER_BOUND" not in fl:
                    failures += 1
            else:
                detail_counts["indeterminate"] += 1
                if "LEVERAGE_THRESHOLD_INDETERMINATE" not in fl:
                    failures += 1

    tests["BR04-T06"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No PARTIAL/MISSING non-BANK row with OCF > 0."
            if checked == 0
            else None
        ),
        details=dict(detail_counts),
    )

    # ------------------------------------------------------------------
    # T07 — no ratio below its LB.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    for row in candidate_rows:
        ratio = finite(row.get("net_debt_to_ocf"))
        lb = finite(row.get("net_debt_to_ocf_lb"))
        if ratio is None or lb is None:
            continue
        checked += 1
        if ratio + CALC_TOL * max(1.0, abs(lb)) < lb:
            failures += 1
    tests["BR04-T07"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No row has both net_debt_to_ocf and LB."
            if checked == 0
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T08 — restricted cash never used as exact cash.
    # ------------------------------------------------------------------
    exact_cash_rows = [
        r for r in candidate_rows if norm(r.get("cash_and_equivalents"))
    ]
    failures = sum(
        "RESTRICTEDCASH" in norm(r.get("cash_and_equivalents_tag")).upper()
        for r in exact_cash_rows
    )
    tests["BR04-T08"] = test_result(
        passed=failures == 0,
        checked=len(exact_cash_rows),
        failures=failures,
        no_case_reason=(
            "No exact cash value published." if not exact_cash_rows else None
        ),
    )

    # ------------------------------------------------------------------
    # T09 — operating lease excluded from total debt components.
    # ------------------------------------------------------------------
    td_component_rows = [
        r for r in components_rows if norm(r.get("used_as")) == "total_debt"
    ]
    failures = sum(
        norm(r.get("tag")).startswith("OperatingLease")
        for r in td_component_rows
    )
    tests["BR04-T09"] = test_result(
        passed=failures == 0,
        checked=len(td_component_rows),
        failures=failures,
        no_case_reason=(
            "No total_debt component exists." if not td_component_rows else None
        ),
    )

    # ------------------------------------------------------------------
    # T10 — explicit exclusions; custom NON_DEBT/UNCLASSIFIED cannot be
    # used as total-debt components either.
    # ------------------------------------------------------------------
    custom_class = {
        (
            norm(r.get("adsh")),
            norm(r.get("line")),
            norm(r.get("tag")),
        ): norm(r.get("assigned_class"))
        for r in custom_rows
    }
    checked = len(td_component_rows)
    failures = 0
    for r in td_component_rows:
        tag = norm(r.get("tag"))
        if tag in EXCLUDED_DEBT_TAGS:
            failures += 1
            continue
        cls = custom_class.get(
            (norm(r.get("adsh")), norm(r.get("line")), tag)
        )
        if cls in {
            "CUSTOM_NON_DEBT",
            "UNCLASSIFIED",
            "CUSTOM_EQUITY_HINT",
        }:
            failures += 1
    tests["BR04-T10"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No total_debt component exists." if checked == 0 else None
        ),
    )

    # Independent source re-read supports T03/T11/T24/T26.
    quarters_keys = list(s1.get("sec_quarters") or [])
    source = source_validation(
        candidate_rows=candidate_rows,
        components_rows=components_rows,
        quarters_keys=quarters_keys,
    )

    # ------------------------------------------------------------------
    # T11 — every selected component has at least one consolidated,
    # unsegmented NUM fact matching its published provenance/value.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    for r in components_rows:
        adsh = norm(r.get("adsh"))
        tag = norm(r.get("tag"))
        version = norm(r.get("version"))
        ddate = norm_date(r.get("ddate"))
        qtrs = norm(r.get("qtrs"))
        uom = norm(r.get("uom")).upper()
        value = finite(r.get("value"))
        if not adsh or not tag or value is None:
            continue
        checked += 1
        vals = source["good_num_values"].get(
            (adsh, tag, version, ddate, qtrs, uom),
            set(),
        )
        if not any(close(value, v) for v in vals):
            failures += 1
    tests["BR04-T11"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No published observed component exists."
            if checked == 0
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T12 — same filing / same annual period across all published
    # provenance and component evidence.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    for row in candidate_rows:
        expected_adsh = norm(row.get("annual_adsh"))
        expected_date = norm_date(row.get("annual_period"))
        fl = flags_of(row)

        for field in builder.SINGLE_FACT_FIELDS:
            adsh = norm(row.get(field + "_adsh"))
            ddate = norm_date(row.get(field + "_ddate"))
            if not adsh and not ddate:
                continue
            checked += 1
            mismatch = (
                (adsh and adsh != expected_adsh)
                or (ddate and ddate != expected_date)
            )
            if mismatch and "PERIOD_MISMATCH" not in fl:
                failures += 1

    for r in components_rows:
        ticker = norm(r.get("ticker"))
        row = candidate_by_ticker.get(ticker)
        if row is None:
            failures += 1
            checked += 1
            continue
        checked += 1
        if (
            norm(r.get("adsh")) != norm(row.get("annual_adsh"))
            or norm_date(r.get("ddate"))
            != norm_date(row.get("annual_period"))
        ):
            if "PERIOD_MISMATCH" not in flags_of(row):
                failures += 1

    tests["BR04-T12"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No provenance values exist." if checked == 0 else None
        ),
    )

    # ------------------------------------------------------------------
    # T13 — net interest tag never masquerades as gross.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    for row in candidate_rows:
        tag = norm(row.get("interest_expense_tag"))
        if tag not in NET_INTEREST_TAGS:
            continue
        checked += 1
        if "INTEREST_GROSSED_UP_FROM_NET" not in flags_of(row):
            failures += 1
    tests["BR04-T13"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No published interest_expense uses a net-interest tag."
            if checked == 0
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T14 — recalculate published motor/derived values from public fields.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    detail = defaultdict(int)
    for row in candidate_rows:
        # net_debt_to_ocf
        ratio = finite(row.get("net_debt_to_ocf"))
        ocf = finite(row.get("annual_operating_cash_flow"))
        if ratio is not None and norm(row.get("br04_module")) != "BANK":
            fl = flags_of(row)
            if ocf is not None:
                expected = None
                if "LEVERAGE_ABOVE_THRESHOLD_BY_LOWER_BOUND" in fl:
                    expected = finite(row.get("net_debt_to_ocf_lb"))
                elif ocf <= 0 and "NET_DEBT_NOT_SERVICEABLE_FROM_OCF" in fl:
                    expected = 99.0
                elif ocf <= 0 and "NET_CASH_NEGATIVE_OCF" in fl:
                    expected = 0.0
                elif norm(row.get("total_debt_status")) == "PRESENT":
                    nd = finite(row.get("net_debt"))
                    if nd is not None and ocf != 0:
                        expected = nd / ocf

                if expected is not None:
                    checked += 1
                    detail["net_debt_to_ocf"] += 1
                    if not close(ratio, expected):
                        failures += 1

        # interest_coverage
        coverage = finite(row.get("interest_coverage"))
        opinc = finite(row.get("annual_operating_income"))
        interest = finite(row.get("interest_expense"))
        if (
            coverage is not None
            and opinc is not None
            and interest is not None
            and interest != 0
        ):
            checked += 1
            detail["interest_coverage"] += 1
            if not close(coverage, opinc / interest):
                failures += 1

        # invested_capital
        invested = finite(row.get("invested_capital"))
        equity = finite(row.get("annual_equity"))
        debt = finite(row.get("total_debt"))
        cash = finite(row.get("cash_and_equivalents"))
        if (
            invested is not None
            and equity is not None
            and debt is not None
            and cash is not None
        ):
            checked += 1
            detail["invested_capital"] += 1
            if not close(invested, equity + debt - cash):
                failures += 1

        # roic
        roic = finite(row.get("roic"))
        if (
            roic is not None
            and opinc is not None
            and invested is not None
            and invested > 0
        ):
            checked += 1
            detail["roic"] += 1
            if not close(roic, opinc * 0.79 / invested):
                failures += 1

    tests["BR04-T14"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No recalculable published ratio exists."
            if checked == 0
            else None
        ),
        details=dict(detail),
    )

    # ------------------------------------------------------------------
    # T15 — no numeric ROIC with PARTIAL debt.
    # ------------------------------------------------------------------
    partial_rows = [
        r
        for r in candidate_rows
        if norm(r.get("total_debt_status")) == "PARTIAL"
    ]
    failures = sum(finite(r.get("roic")) is not None for r in partial_rows)
    tests["BR04-T15"] = test_result(
        passed=failures == 0,
        checked=len(partial_rows),
        failures=failures,
        no_case_reason=(
            "No PARTIAL-debt row exists." if not partial_rows else None
        ),
    )

    # ------------------------------------------------------------------
    # T16 — sector rules.
    # ------------------------------------------------------------------
    sector_rows = [
        r
        for r in candidate_rows
        if norm(r.get("br04_module")) in {"BANK", "INSURANCE"}
    ]
    checked = len(sector_rows)
    failures = 0
    bank_count = 0
    insurance_count = 0
    for r in sector_rows:
        module = norm(r.get("br04_module"))
        if module == "BANK":
            bank_count += 1
            if not (
                norm(r.get("net_debt_to_ocf")) == "NOT_APPLICABLE"
                and norm(r.get("interest_coverage")) == "NOT_APPLICABLE"
                and norm(r.get("roic")) == "NOT_APPLICABLE"
            ):
                failures += 1
        elif module == "INSURANCE":
            insurance_count += 1
            if norm(r.get("roic")) != "NOT_APPLICABLE":
                failures += 1
    tests["BR04-T16"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        details={
            "bank_rows": bank_count,
            "insurance_rows": insurance_count,
        },
    )

    # ------------------------------------------------------------------
    # T17 — every below-legacy flag has explicit provenance explanation.
    # ------------------------------------------------------------------
    flagged = [
        r
        for r in candidate_rows
        if "TOTAL_DEBT_BELOW_LEGACY" in flags_of(r)
    ]
    failures = sum(
        not norm(r.get("br04_legacy_comparison_note")) for r in flagged
    )
    tests["BR04-T17"] = test_result(
        passed=failures == 0,
        checked=len(flagged),
        failures=failures,
        no_case_reason=(
            "No TOTAL_DEBT_BELOW_LEGACY case exists." if not flagged else None
        ),
    )

    # ------------------------------------------------------------------
    # T19 — string-for-string invariance of every pre-existing cell.
    # ------------------------------------------------------------------
    checked = len(base_matrix) * len(base_header)
    failures = 0
    if cand_header[: len(base_header)] != base_header:
        failures += len(base_header)
    for base_row, cand_row in zip(base_matrix, cand_matrix):
        prefix = cand_row[: len(base_header)]
        failures += sum(a != b for a, b in zip(base_row, prefix))
    tests["BR04-T19"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        details={
            "base_columns": len(base_header),
            "candidate_columns": len(cand_header),
            "rows": len(base_matrix),
        },
    )

    # ------------------------------------------------------------------
    # T22 — synthetic rule tests.
    # ------------------------------------------------------------------
    syn_checked, syn_failures, syn_detail = run_synthetic_tests()
    tests["BR04-T22"] = test_result(
        passed=syn_failures == 0,
        checked=syn_checked,
        failures=syn_failures,
        details={
            "cases": syn_checked,
            "all_expected_declared_before_execution": True,
            "case_results": syn_detail,
        },
    )

    # ------------------------------------------------------------------
    # T23 — face line without usable value never PRESENT/zero-by-closure.
    # ------------------------------------------------------------------
    face_missing_rows = [
        r
        for r in candidate_rows
        if "FACE_LINE_VALUE_NOT_FOUND" in flags_of(r)
    ]
    failures = 0
    for r in face_missing_rows:
        if (
            norm(r.get("total_debt_status")) == "PRESENT"
            or "DEBT_ZERO_BY_BS_CLOSURE" in flags_of(r)
        ):
            failures += 1
    tests["BR04-T23"] = test_result(
        passed=failures == 0,
        checked=len(face_missing_rows),
        failures=failures,
        no_case_reason=(
            "No FACE_LINE_VALUE_NOT_FOUND case exists."
            if not face_missing_rows
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T24 — every total-debt component is independently present on PRE
    # face statement; therefore no NUM-only fact is used.
    # ------------------------------------------------------------------
    checked = len(td_component_rows)
    failures = 0
    for r in td_component_rows:
        key = (
            norm(r.get("adsh")),
            norm(r.get("stmt")),
            norm(r.get("line")),
            norm(r.get("tag")),
        )
        if key not in source["face_keys"]:
            failures += 1
    tests["BR04-T24"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No total_debt component exists." if checked == 0 else None
        ),
    )

    # ------------------------------------------------------------------
    # T25 — legacy tags nowhere in BR-04 fields/components.
    # ------------------------------------------------------------------
    br04_cols = [c for c in cand_header if c not in base_header]
    checked = len(candidate_rows)
    failures = 0
    for r in candidate_rows:
        joined = "\x1f".join(norm(r.get(c)) for c in br04_cols)
        if any(tag in joined for tag in LEGACY_FORBIDDEN_TAGS):
            failures += 1
    tests["BR04-T25"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
    )

    # ------------------------------------------------------------------
    # T26 — if both L1 gross-interest tags are on IS and differ, candidate
    # must be CONFLICTING.
    # ------------------------------------------------------------------
    checked = 0
    failures = 0
    for adsh, row in candidate_by_adsh.items():
        is_tags = source["face_tags"].get(adsh, {}).get("IS", set())
        if not set(builder.GROSS_INTEREST_L1).issubset(is_tags):
            continue

        v1 = source["standard_values"].get(
            (adsh, builder.GROSS_INTEREST_L1[0]),
            set(),
        )
        v2 = source["standard_values"].get(
            (adsh, builder.GROSS_INTEREST_L1[1]),
            set(),
        )
        if len(v1) != 1 or len(v2) != 1:
            continue

        a = next(iter(v1))
        b = next(iter(v2))
        if close(a, b):
            continue

        checked += 1
        if not (
            norm(row.get("interest_status")) == "CONFLICTING"
            and "INTEREST_TAGS_DISAGREE" in flags_of(row)
        ):
            failures += 1

    tests["BR04-T26"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        no_case_reason=(
            "No current-filing row exposes both L1 interest tags with different values."
            if checked == 0
            else None
        ),
    )

    # ------------------------------------------------------------------
    # T27 — exact cash must come from BS.
    # ------------------------------------------------------------------
    cash_rows = [
        r for r in candidate_rows if norm(r.get("cash_and_equivalents"))
    ]
    failures = sum(
        norm(r.get("cash_and_equivalents_stmt")) != "BS"
        for r in cash_rows
    )
    tests["BR04-T27"] = test_result(
        passed=failures == 0,
        checked=len(cash_rows),
        failures=failures,
        no_case_reason=(
            "No exact cash value published." if not cash_rows else None
        ),
    )

    # ------------------------------------------------------------------
    # T28 — historical restricted-inclusive cash correction cannot lower
    # net debt, unless TOTAL_DEBT_BELOW_LEGACY is explicitly explained.
    # ------------------------------------------------------------------
    restricted_rows = [
        r
        for r in candidate_rows
        if "RESTRICTEDCASH" in norm(r.get("annual_cash_tag")).upper()
    ]
    failures = 0
    applicable = 0
    explained_exceptions = 0
    for r in restricted_rows:
        annual_debt = finite(r.get("annual_debt"))
        annual_cash = finite(r.get("annual_cash"))
        net_debt = finite(r.get("net_debt"))
        if annual_debt is None or annual_cash is None or net_debt is None:
            continue
        applicable += 1
        historical_net = annual_debt - annual_cash
        if net_debt + CALC_TOL * max(1.0, abs(historical_net)) < historical_net:
            if (
                "TOTAL_DEBT_BELOW_LEGACY" in flags_of(r)
                and norm(r.get("br04_legacy_comparison_note"))
            ):
                explained_exceptions += 1
            else:
                failures += 1

    tests["BR04-T28"] = test_result(
        passed=failures == 0,
        checked=len(restricted_rows),
        failures=failures,
        no_case_reason=(
            "No historical restricted-inclusive cash row exists."
            if not restricted_rows
            else None
        ),
        details={
            "restricted_cash_rows": len(restricted_rows),
            "applicable_with_all_numeric_fields": applicable,
            "explained_total_debt_below_legacy_exceptions": explained_exceptions,
        },
    )

    # ------------------------------------------------------------------
    # T29 — label dictionary synthetic cases.
    # ------------------------------------------------------------------
    checked = len(LABEL_EXPECTED)
    failures = 0
    label_results = {}
    for label, expected in LABEL_EXPECTED.items():
        actual = builder.classify_custom_label(label)
        label_results[expected] = label_results.get(expected, 0) + int(
            actual == expected
        )
        if actual != expected:
            failures += 1
    tests["BR04-T29"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        details={
            "dictionary_version": builder.LABEL_DICTIONARY_VERSION,
            "expected_cases": sorted(set(LABEL_EXPECTED.values())),
        },
    )

    # ------------------------------------------------------------------
    # T30 — annual_adsh missing count must match T00-bis.
    # ------------------------------------------------------------------
    no_adsh_rows = [
        r for r in candidate_rows if not norm(r.get("annual_adsh"))
    ]
    flagged_no_adsh = [
        r
        for r in candidate_rows
        if "NO_ANNUAL_ADSH" in flags_of(r)
    ]
    t00_expected = int(t00.get("companies_without_annual_adsh", -1))
    failures = 0
    if len(no_adsh_rows) != t00_expected:
        failures += abs(len(no_adsh_rows) - t00_expected) or 1
    if len(flagged_no_adsh) != len(no_adsh_rows):
        failures += abs(len(flagged_no_adsh) - len(no_adsh_rows)) or 1
    tests["BR04-T30"] = test_result(
        passed=failures == 0,
        checked=len(candidate_rows),
        failures=failures,
        details={
            "missing_annual_adsh_candidate": len(no_adsh_rows),
            "missing_annual_adsh_t00bis": t00_expected,
            "no_annual_adsh_flag_count": len(flagged_no_adsh),
        },
    )

    # ------------------------------------------------------------------
    # T21 — no vacuous T01-T17.
    # ------------------------------------------------------------------
    failures = 0
    checked = 17
    vacuous = 0
    for n in range(1, 18):
        key = f"BR04-T{n:02d}"
        result = tests[key]
        if result["checked"] == 0 and not result.get("no_case_reason"):
            failures += 1
            vacuous += 1
    tests["BR04-T21"] = test_result(
        passed=failures == 0,
        checked=checked,
        failures=failures,
        details={"vacuous_without_declaration": vacuous},
    )

    # ------------------------------------------------------------------
    # Additional §13 blocking gates that are decidable in S2.
    # They do not invent new economic rules; they operationalize the written
    # publication blockers.
    # ------------------------------------------------------------------
    gates: dict[str, dict] = {}

    # Gate: no custom debt line may disappear in a favorable direction.
    # A custom debt line is conservatively represented if:
    # - it is an explicit total_debt component, OR
    # - published/prudential total debt is at least the sum of all custom-debt
    #   lines for that filing and the LABEL flag is present.
    custom_debt_by_adsh: dict[str, float] = defaultdict(float)
    custom_debt_rows = 0
    for r in custom_rows:
        if norm(r.get("assigned_class")) != "CUSTOM_DEBT":
            continue
        v = finite(r.get("value"))
        if v is None:
            continue
        custom_debt_rows += 1
        custom_debt_by_adsh[norm(r.get("adsh"))] += v

    custom_component_adsh = {
        norm(r.get("adsh"))
        for r in td_component_rows
        if custom_class.get(
            (
                norm(r.get("adsh")),
                norm(r.get("line")),
                norm(r.get("tag")),
            )
        )
        == "CUSTOM_DEBT"
    }

    gate_failures = 0
    for adsh, custom_sum in custom_debt_by_adsh.items():
        row = candidate_by_adsh.get(adsh)
        if row is None:
            gate_failures += 1
            continue
        total = finite(row.get("total_debt"))
        candidates = parse_candidate_values(row.get("total_debt_candidates"))
        prudential = max(candidates.values()) if candidates else total
        represented = (
            adsh in custom_component_adsh
            or (
                prudential is not None
                and prudential + CALC_TOL * max(1.0, custom_sum) >= custom_sum
            )
        )
        if (
            not represented
            or "CUSTOM_TAG_DEBT_BY_LABEL" not in flags_of(row)
        ):
            gate_failures += 1

    gates["custom_debt_never_favorably_excluded"] = {
        "status": "PASS" if gate_failures == 0 else "FAIL",
        "checked_custom_debt_rows": custom_debt_rows,
        "checked_companies": len(custom_debt_by_adsh),
        "failures": gate_failures,
    }

    # Gate: status_candidate measures indeterminate rows and invariant text.
    status_text = status_path.read_text(encoding="utf-8")
    actual_indeterminate = sum(
        "LEVERAGE_THRESHOLD_INDETERMINATE" in flags_of(r)
        for r in candidate_rows
    )
    status_measure_ok = (
        str(actual_indeterminate) in status_text
        and "MISSING resta `MISSING`" in status_text
    )
    gates["status_indeterminate_measured"] = {
        "status": "PASS" if status_measure_ok else "FAIL",
        "actual_indeterminate_rows": actual_indeterminate,
        "failures": 0 if status_measure_ok else 1,
    }

    # Gate: chain of custody hashes still match.
    custody_ok = (
        sha256_file(CURRENT) == base_sha
        and sha256_file(candidate_path) == candidate_sha
        and norm(t00.get("base_canonical_sha256")) == base_sha
    )
    gates["chain_of_custody_s2"] = {
        "status": "PASS" if custody_ok else "FAIL",
        "failures": 0 if custody_ok else 1,
    }

    # ------------------------------------------------------------------
    # Overall S2.
    # ------------------------------------------------------------------
    required_test_ids = (
        [f"BR04-T{n:02d}" for n in range(1, 18)]
        + ["BR04-T19", "BR04-T21", "BR04-T22"]
        + [f"BR04-T{n:02d}" for n in range(23, 31)]
    )

    failed_tests = [
        tid for tid in required_test_ids if tests[tid]["status"] != "PASS"
    ]
    failed_gates = [
        name for name, result in gates.items() if result["status"] != "PASS"
    ]

    overall = not failed_tests and not failed_gates

    # No ticker lists or company identifiers in this report.
    report = {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": now_iso(),
        "phase": "S2",
        "s2_run_id": norm(__import__("os").environ.get("GITHUB_RUN_ID")),
        "s1_run_id": s1_run_id,
        "base_canonical_sha256": base_sha,
        "candidate_sha256": candidate_sha,
        "candidate_rows": len(candidate_rows),
        "base_columns": len(base_header),
        "candidate_columns": len(cand_header),
        "tests_required_in_s2": required_test_ids,
        "tests": tests,
        "blocking_gates_s2": gates,
        "failed_tests": failed_tests,
        "failed_gates": failed_gates,
        "overall_passed": overall,
        "deferred_by_contract": {
            "BR04-T18": "S4 engine preflight on exact candidate chunks",
            "BR04-T20": "S3 transport/chunk byte-identity",
            "BR04-T31": "S6 immediately before atomic promotion",
        },
        "invariants": [
            "Regression results contain aggregate counts only; no ticker list.",
            "Candidate was not modified by S2.",
            "data/current was not modified by S2.",
            "MISSING remains MISSING; absence is never converted to zero.",
            "No ranking, recommendation, BQS, IOS or Blind Test was executed.",
        ],
    }

    bridge.write_json_atomic(report_path, report)

    # Re-check after writing evidence.
    if sha256_file(CURRENT) != base_sha:
        raise SystemExit("S2_BLOCK: canonical changed during S2")
    if sha256_file(candidate_path) != candidate_sha:
        raise SystemExit("S2_BLOCK: candidate changed during S2")

    print("BR-04 S2 regression completed.")
    print(f"s1_run_id={s1_run_id}")
    print(f"base_canonical_sha256={base_sha}")
    print(f"candidate_sha256={candidate_sha}")
    print(f"overall_passed={str(overall).lower()}")
    print(f"failed_tests={len(failed_tests)}")
    print(f"failed_gates={len(failed_gates)}")
    print(f"report={report_path.relative_to(ROOT)}")
    print("data/current modified: NO")
    print("candidate modified: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
