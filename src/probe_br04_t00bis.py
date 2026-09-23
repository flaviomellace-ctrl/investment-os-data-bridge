#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-04 T00-bis census probe (v1.1).

Pre-candidate census required by BR04_DATA_CONTRACT_V4_1_POST_T00_R3.

Safety:
- pins data/current/sp500_fundamentals.csv by SHA-256;
- writes only data/staging/br04/<run_id>/evidence/;
- never writes data/current/;
- never creates a BR-04 candidate;
- never computes BQS, IOS, rankings, recommendations or Blind Test results.

v1.1 correction:
- every face-statement census is scoped to the statement required by the
  frozen contract:
    debt/cash/LSE -> BS
    gross/net interest and interest income -> IS
    InterestPaidNet -> CF
- a "usable annual" fact counts only when the same tag is also present on the
  required face statement for that filing.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import bridge


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DIR = ROOT / "data" / "current"
FUNDAMENTALS_PATH = CURRENT_DIR / "sp500_fundamentals.csv"

SEC_QUARTERS = 16
SCHEMA = "br04_t00bis_probe_v1.2"

RUN_ID = (
    os.getenv("GITHUB_RUN_ID", "").strip()
    or datetime.now(timezone.utc).strftime("local_%Y%m%dT%H%M%SZ")
)
EVIDENCE_DIR = ROOT / "data" / "staging" / "br04" / RUN_ID / "evidence"
JSON_PATH = EVIDENCE_DIR / "br04_t00bis_report.json"
MD_PATH = EVIDENCE_DIR / "br04_t00bis_report.md"


CURRENT_DEBT_TAGS = {
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "CommercialPaper",
    "LinesOfCreditCurrent",
    "NotesPayableCurrent",
    "SecuredDebtCurrent",
    "UnsecuredDebtCurrent",
    "ConvertibleNotesPayableCurrent",
    "OtherShortTermBorrowings",
    "FinanceLeaseLiabilityCurrent",
    "LongTermDebtAndCapitalLeaseObligationsCurrent",
    "DebtCurrent",
}

NONCURRENT_DEBT_TAGS = {
    "LongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations",
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
    "FinanceLeaseLiabilityNoncurrent",
}

DEBT_AGGREGATE_TAGS = {
    "LongTermDebt",
    "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
    "DebtAndCapitalLeaseObligations",
    "DebtLongtermAndShorttermCombinedAmount",
    "FinanceLeaseLiability",
}

GROSS_INTEREST_L1_TAGS = {
    "InterestExpenseNonoperating",
    "InterestExpense",
}

GROSS_INTEREST_L2_TAGS = {
    "InterestExpenseDebt",
    "InterestAndDebtExpense",
}

NET_INTEREST_TAGS = {
    "InterestIncomeExpenseNonoperatingNet",
    "InterestIncomeExpenseNet",
    "InterestRevenueExpenseNet",
}

INTEREST_PAID_TAG = "InterestPaidNet"
INTEREST_INCOME_TAG = "InvestmentIncomeInterest"

EXACT_CASH_TAGS = {
    "CashAndCashEquivalentsAtCarryingValue",
    "Cash",
}

BALANCE_CONTROL_TAGS = {
    "Liabilities",
    "LiabilitiesAndStockholdersEquity",
    "StockholdersEquity",
}

LEGACY_FORBIDDEN_TAGS = {
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
}

ALL_SCAN_TAGS = sorted(
    CURRENT_DEBT_TAGS
    | NONCURRENT_DEBT_TAGS
    | DEBT_AGGREGATE_TAGS
    | GROSS_INTEREST_L1_TAGS
    | GROSS_INTEREST_L2_TAGS
    | NET_INTEREST_TAGS
    | {INTEREST_PAID_TAG, INTEREST_INCOME_TAG}
    | EXACT_CASH_TAGS
    | BALANCE_CONTROL_TAGS
    | LEGACY_FORBIDDEN_TAGS
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

# Diagnostic only, not a new economic classification rule.
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

PASSIVE_HINT_RE = re.compile(
    r"\b("
    r"liabilit(?:y|ies)|payable|obligation|debt|borrow|note|loan|credit|"
    r"commercial\s+paper|bond|lease|equity|capital|retained\s+earnings|"
    r"accumulated\s+deficit|treasury\s+stock|noncontrolling|minority"
    r")\b",
    flags=re.I,
)


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
    return str(value).strip()


def norm_date(value) -> str:
    text = norm_text(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else digits


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


def load_universe() -> tuple[pd.DataFrame, dict[str, str]]:
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato")

    df = pd.read_csv(FUNDAMENTALS_PATH, low_memory=False)
    required = {"ticker", "annual_adsh", "annual_period"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(
            "Colonne mancanti nel fundamentals: " + ", ".join(sorted(missing))
        )
    if df["ticker"].duplicated().any():
        raise SystemExit("Ticker duplicati nel fundamentals")

    adsh_to_period: dict[str, str] = {}
    for _, row in df[["annual_adsh", "annual_period"]].iterrows():
        adsh = norm_text(row["annual_adsh"])
        period = norm_date(row["annual_period"])
        if adsh:
            adsh_to_period[adsh] = period

    return df, adsh_to_period


def classify_custom_label(label: str) -> str:
    debt = bool(DEBT_LABEL_RE.search(label or ""))
    non_debt = bool(NON_DEBT_LABEL_RE.search(label or ""))

    # R3 §5.5: collision -> debt, conservatively.
    if debt:
        return "CUSTOM_DEBT"
    if non_debt:
        return "CUSTOM_NON_DEBT"
    if EQUITY_HINT_RE.search(label or ""):
        return "CUSTOM_EQUITY_HINT"
    return "UNCLASSIFIED"


def annual_fact_usable(rows: pd.DataFrame, *, flow: bool) -> bool:
    if rows.empty:
        return False

    work = rows.copy()
    work["value_num"] = pd.to_numeric(work.get("value"), errors="coerce")
    work = work[work["value_num"].notna()]
    if work.empty:
        return False

    if "uom" in work.columns:
        usd = work[work["uom"].fillna("").str.upper().eq("USD")]
        if not usd.empty:
            work = usd

    if flow:
        if "qtrs" not in work.columns:
            return False
        qtrs = pd.to_numeric(work["qtrs"], errors="coerce")
        work = work[qtrs.eq(4)]
        if work.empty:
            return False

    return True


def union_for(mapping: dict[str, set[str]], tags: set[str]) -> set[str]:
    out: set[str] = set()
    for tag in tags:
        out |= mapping[tag]
    return out


def face_union(
    face_by_stmt: dict[str, dict[str, set[str]]],
    tags: set[str],
    stmt: str,
) -> set[str]:
    out: set[str] = set()
    for tag in tags:
        out |= face_by_stmt[tag][stmt]
    return out


def usable_on_required_face(
    usable_num_tags: dict[str, set[str]],
    face_by_stmt: dict[str, dict[str, set[str]]],
    tags: set[str],
    stmt: str,
) -> set[str]:
    out: set[str] = set()
    for tag in tags:
        out |= usable_num_tags[tag] & face_by_stmt[tag][stmt]
    return out


def main() -> int:
    fundamentals, adsh_to_period = load_universe()
    annual_adshs = set(adsh_to_period)

    # Company counts must be row-based. Multiple share classes can legitimately
    # point to the same annual ADSH, so len(unique ADSH) is NOT the number of
    # companies with an annual filing.
    annual_adsh_row_count = int(
        fundamentals["annual_adsh"].map(norm_text).ne("").sum()
    )
    missing_annual_adsh_row_count = len(fundamentals) - annual_adsh_row_count
    unique_annual_adsh_count = len(annual_adshs)

    base_sha = sha256_file(FUNDAMENTALS_PATH)
    base_git_sha = os.getenv("GITHUB_SHA", "").strip()

    downloader = bridge.Downloader()
    quarters, sec_index_meta = bridge.discover_sec_quarters(downloader)
    selected = quarters[-SEC_QUARTERS:]

    # tag -> stmt -> annual ADSHs where the tag is on the required face statement.
    face_by_stmt: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    # tag -> annual ADSHs with a consolidated, unsegmented, same-period NUM fact.
    usable_num_tags: dict[str, set[str]] = defaultdict(set)

    custom_counts = defaultdict(int)
    custom_company_sets: dict[str, set[str]] = defaultdict(set)
    custom_any_unclassified: set[str] = set()
    custom_passive_unclassified: set[str] = set()

    lse_face: set[str] = set()
    legacy_observed: set[str] = set()

    print(
        f"BR04-T00-bis v1.1: universe={len(fundamentals)}, "
        f"annual_adsh={len(annual_adshs)}, base_sha256={base_sha}"
    )

    with tempfile.TemporaryDirectory(prefix="investment_os_br04_t00bis_") as td:
        td_path = Path(td)

        for q in selected:
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

                relevant = face[face["tag"].isin(ALL_SCAN_TAGS)]
                for (tag, stmt), grp in relevant.groupby(["tag", "stmt"]):
                    face_by_stmt[tag][stmt].update(
                        grp["adsh"].dropna().astype(str)
                    )

                lse_face.update(
                    face.loc[
                        (face["stmt"].eq("BS"))
                        & face["tag"].eq("LiabilitiesAndStockholdersEquity"),
                        "adsh",
                    ].dropna().astype(str)
                )

                legacy_observed.update(
                    face.loc[
                        (face["stmt"].eq("BS"))
                        & face["tag"].isin(LEGACY_FORBIDDEN_TAGS),
                        "adsh",
                    ].dropna().astype(str)
                )

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

                bs = face[face["stmt"].eq("BS")].copy()
                if custom_pairs and not bs.empty:
                    pairs = list(
                        zip(
                            bs["tag"].fillna(""),
                            bs["version"].fillna(""),
                        )
                    )
                    bs["_is_custom"] = [p in custom_pairs for p in pairs]

                    for _, row in bs[bs["_is_custom"]].iterrows():
                        adsh = norm_text(row.get("adsh"))
                        label = norm_text(row.get("plabel"))
                        cls = classify_custom_label(label)

                        custom_counts[f"{cls}_rows"] += 1
                        if adsh:
                            custom_company_sets[cls].add(adsh)

                        if cls == "UNCLASSIFIED" and adsh:
                            custom_any_unclassified.add(adsh)
                            if PASSIVE_HINT_RE.search(label):
                                custom_passive_unclassified.add(adsh)

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
                        if "adsh" not in chunk.columns or "tag" not in chunk.columns:
                            raise bridge.BridgeError(
                                f"NUM SEC {q.key}: colonne adsh/tag assenti"
                            )

                        mask = (
                            chunk["adsh"].isin(annual_adshs)
                            & chunk["tag"].isin(ALL_SCAN_TAGS)
                        )
                        if "coreg" in chunk.columns:
                            mask &= chunk["coreg"].fillna("").eq("")
                        if "segments" in chunk.columns:
                            mask &= chunk["segments"].fillna("").eq("")

                        part = chunk.loc[mask].copy()
                        if part.empty or "ddate" not in part.columns:
                            continue

                        part["ddate_norm"] = part["ddate"].map(norm_date)
                        expected = part["adsh"].map(adsh_to_period)
                        part = part[part["ddate_norm"].eq(expected)].copy()
                        if part.empty:
                            continue

                        flow_tags = (
                            GROSS_INTEREST_L1_TAGS
                            | GROSS_INTEREST_L2_TAGS
                            | NET_INTEREST_TAGS
                            | {INTEREST_PAID_TAG, INTEREST_INCOME_TAG}
                        )

                        for (adsh, tag), grp in part.groupby(["adsh", "tag"]):
                            if annual_fact_usable(
                                grp,
                                flow=(tag in flow_tags),
                            ):
                                usable_num_tags[tag].add(str(adsh))

    gross_tags = GROSS_INTEREST_L1_TAGS | GROSS_INTEREST_L2_TAGS

    # Frozen statement scope:
    # debt/cash/LSE = BS, gross/net/income interest = IS, paid interest = CF.
    gross_face = face_union(face_by_stmt, gross_tags, "IS")
    gross_usable = usable_on_required_face(
        usable_num_tags, face_by_stmt, gross_tags, "IS"
    )

    net_face = face_union(face_by_stmt, NET_INTEREST_TAGS, "IS")
    net_usable = usable_on_required_face(
        usable_num_tags, face_by_stmt, NET_INTEREST_TAGS, "IS"
    )

    paid_face = face_by_stmt[INTEREST_PAID_TAG]["CF"]
    paid_usable = (
        usable_num_tags[INTEREST_PAID_TAG]
        & face_by_stmt[INTEREST_PAID_TAG]["CF"]
    )

    income_face = face_by_stmt[INTEREST_INCOME_TAG]["IS"]
    income_usable = (
        usable_num_tags[INTEREST_INCOME_TAG]
        & face_by_stmt[INTEREST_INCOME_TAG]["IS"]
    )

    exact_cash_face = face_union(face_by_stmt, EXACT_CASH_TAGS, "BS")
    exact_cash_usable = usable_on_required_face(
        usable_num_tags, face_by_stmt, EXACT_CASH_TAGS, "BS"
    )

    current_face = face_union(face_by_stmt, CURRENT_DEBT_TAGS, "BS")
    current_usable = usable_on_required_face(
        usable_num_tags, face_by_stmt, CURRENT_DEBT_TAGS, "BS"
    )

    noncurrent_face = face_union(face_by_stmt, NONCURRENT_DEBT_TAGS, "BS")
    noncurrent_usable = usable_on_required_face(
        usable_num_tags, face_by_stmt, NONCURRENT_DEBT_TAGS, "BS"
    )

    aggregate_face = face_union(face_by_stmt, DEBT_AGGREGATE_TAGS, "BS")
    aggregate_usable = usable_on_required_face(
        usable_num_tags, face_by_stmt, DEBT_AGGREGATE_TAGS, "BS"
    )

    all_debt_face = current_face | noncurrent_face | aggregate_face
    all_debt_usable = current_usable | noncurrent_usable | aggregate_usable

    only_net_face = net_face - gross_face - paid_face
    only_net_usable = net_usable - gross_usable - paid_usable

    only_paid_face = paid_face - gross_face - net_face
    only_paid_usable = paid_usable - gross_usable - net_usable

    net_plus_income_face = net_face & income_face
    net_plus_income_usable = net_usable & income_usable
    net_plus_income_no_gross_face = net_plus_income_face - gross_face
    net_plus_income_no_gross_usable = net_plus_income_usable - gross_usable

    lse_usable = (
        usable_num_tags["LiabilitiesAndStockholdersEquity"]
        & face_by_stmt["LiabilitiesAndStockholdersEquity"]["BS"]
    )

    # R3 §7.2 requires proof that the sum of all leaf liabilities/equity
    # reconstructs LSE. SEC FSDS PRE exposes statement/report/line ordering but
    # not a parent-child presentation/calculation tree. Do not fabricate leaves.
    closure = {
        "strict_closure_demonstration_supported_by_current_fsds": False,
        "closure_demonstrated_companies": None,
        "blocker": "PRE_HAS_ORDER_BUT_NO_PARENT_CHILD_OR_CALCULATION_HIERARCHY",
        "companies_with_LSE_on_face": len(lse_face),
        "companies_with_usable_LSE_annual_fact": len(lse_usable),
        "companies_without_passive_hint_custom_unclassified": len(
            annual_adshs - custom_passive_unclassified
        ),
    }

    report = {
        "schema": SCHEMA,
        "generated_at_utc": now_iso(),
        "run_id": RUN_ID,
        "purpose": "BR04-T00-bis pre-candidate census only",
        "base_canonical_sha256": base_sha,
        "base_git_sha": base_git_sha,
        "candidate_sha256": None,
        "candidate_sha256_exemption": (
            "T00-bis is pre-candidate under R3 §17.6"
        ),
        "universe_rows": len(fundamentals),
        "companies_with_annual_adsh": annual_adsh_row_count,
        "companies_without_annual_adsh": missing_annual_adsh_row_count,
        "unique_annual_adsh_filings": unique_annual_adsh_count,
        "annual_adsh_counting_rule": "company rows, not unique ADSH values",
        "quarters_used": [q.key for q in selected],
        "sec_index": sec_index_meta,
        "statement_scope": {
            "debt": "BS",
            "cash": "BS",
            "liabilities_and_equity_control": "BS",
            "gross_interest": "IS",
            "net_interest": "IS",
            "interest_income": "IS",
            "interest_paid": "CF",
        },
        "interest_unions": {
            "gross_l1_or_l2_face": len(gross_face),
            "gross_l1_or_l2_usable_annual": len(gross_usable),
            "only_net_face": len(only_net_face),
            "only_net_usable_annual": len(only_net_usable),
            "only_interest_paid_face": len(only_paid_face),
            "only_interest_paid_usable_annual": len(only_paid_usable),
            "net_plus_interest_income_face": len(net_plus_income_face),
            "net_plus_interest_income_usable_annual": len(net_plus_income_usable),
            "net_plus_interest_income_no_gross_face": len(
                net_plus_income_no_gross_face
            ),
            "net_plus_interest_income_no_gross_usable_annual": len(
                net_plus_income_no_gross_usable
            ),
        },
        "cash_union": {
            "exact_cash_face_BS": len(exact_cash_face),
            "exact_cash_usable_annual_BS": len(exact_cash_usable),
        },
        "debt_class_unions": {
            "current_face_BS": len(current_face),
            "current_usable_annual_BS": len(current_usable),
            "noncurrent_face_BS": len(noncurrent_face),
            "noncurrent_usable_annual_BS": len(noncurrent_usable),
            "aggregate_face_BS": len(aggregate_face),
            "aggregate_usable_annual_BS": len(aggregate_usable),
            "any_debt_face_BS": len(all_debt_face),
            "any_debt_usable_annual_BS": len(all_debt_usable),
        },
        "custom_label_census": {
            "custom_debt_rows": custom_counts["CUSTOM_DEBT_rows"],
            "custom_debt_companies": len(custom_company_sets["CUSTOM_DEBT"]),
            "custom_non_debt_rows": custom_counts["CUSTOM_NON_DEBT_rows"],
            "custom_non_debt_companies": len(
                custom_company_sets["CUSTOM_NON_DEBT"]
            ),
            "custom_equity_hint_rows": custom_counts["CUSTOM_EQUITY_HINT_rows"],
            "custom_equity_hint_companies": len(
                custom_company_sets["CUSTOM_EQUITY_HINT"]
            ),
            "custom_unclassified_rows_all_BS": custom_counts["UNCLASSIFIED_rows"],
            "custom_unclassified_companies_all_BS": len(custom_any_unclassified),
            "custom_unclassified_companies_passive_hint": len(
                custom_passive_unclassified
            ),
        },
        "closure": closure,
        "legacy_forbidden_tags": {
            "companies_observed_on_BS_face": len(legacy_observed),
            "must_be_zero_under_R3": True,
        },
        "rules": [
            "No canonical file is modified.",
            "T00-bis records base_canonical_sha256 and is exempt from candidate_sha256.",
            "Face statement means PRE inpth=0 on the statement required by the frozen contract.",
            "Usable annual fact must also be present on that required face statement.",
            "Usable annual fact means same annual_adsh, same annual_period, consolidated and unsegmented; flow tags require qtrs=4.",
            "Net interest is never counted as gross interest.",
            "Custom label collision between debt and non-debt dictionaries resolves to debt conservatively.",
            "Strict balance-sheet closure is not fabricated when PRE lacks parent-child/calculation hierarchy.",
            "No ticker is written to the report.",
            "No BQS, IOS, ranking, recommendation or Blind Test is executed.",
        ],
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    bridge.write_json_atomic(JSON_PATH, report)

    md = [
        "# BR-04 T00-bis — pre-candidate census v1.1",
        "",
        f"- Run ID: **{RUN_ID}**",
        f"- Base canonical SHA-256: `{base_sha}`",
        "- Candidate SHA-256: **N/A — pre-candidate exemption (R3 §17.6)**",
        f"- Universe: **{len(fundamentals)}**",
        f"- Company rows with annual ADSH: **{annual_adsh_row_count}**",
        f"- Company rows without annual ADSH: **{missing_annual_adsh_row_count}**",
        f"- Unique annual ADSH filings: **{unique_annual_adsh_count}**",
        "- Counting rule: **company rows, not unique ADSH values**",
        f"- SEC quarters: **{len(selected)}** "
        f"({selected[0].key} → {selected[-1].key})",
        "",
        "## Interest unions — statement scoped",
        "",
        f"- Gross L1/L2 on IS face: **{len(gross_face)}**",
        f"- Gross L1/L2 usable annual + IS face: **{len(gross_usable)}**",
        f"- Only net on IS face: **{len(only_net_face)}**",
        f"- Only net usable annual + IS face: **{len(only_net_usable)}**",
        f"- Only InterestPaidNet on CF face: **{len(only_paid_face)}**",
        f"- Only InterestPaidNet usable annual + CF face: **{len(only_paid_usable)}**",
        f"- Net + InvestmentIncomeInterest on IS face: **{len(net_plus_income_face)}**",
        f"- Net + InvestmentIncomeInterest usable annual + IS face: **{len(net_plus_income_usable)}**",
        f"- Net + income, no gross, on IS face: **{len(net_plus_income_no_gross_face)}**",
        f"- Net + income, no gross, usable annual + IS face: **{len(net_plus_income_no_gross_usable)}**",
        "",
        "## Exact cash — BS only",
        "",
        f"- Exact cash on BS face: **{len(exact_cash_face)}**",
        f"- Exact cash usable annual + BS face: **{len(exact_cash_usable)}**",
        "",
        "## Debt classes — BS only",
        "",
        f"- Current debt face / usable: **{len(current_face)} / {len(current_usable)}**",
        f"- Noncurrent debt face / usable: **{len(noncurrent_face)} / {len(noncurrent_usable)}**",
        f"- Debt aggregate face / usable: **{len(aggregate_face)} / {len(aggregate_usable)}**",
        f"- Any debt face / usable: **{len(all_debt_face)} / {len(all_debt_usable)}**",
        "",
        "## Custom labels",
        "",
        f"- CUSTOM_DEBT rows / companies: **{custom_counts['CUSTOM_DEBT_rows']} / "
        f"{len(custom_company_sets['CUSTOM_DEBT'])}**",
        f"- CUSTOM_NON_DEBT rows / companies: **{custom_counts['CUSTOM_NON_DEBT_rows']} / "
        f"{len(custom_company_sets['CUSTOM_NON_DEBT'])}**",
        f"- Equity-hint rows / companies (diagnostic): **{custom_counts['CUSTOM_EQUITY_HINT_rows']} / "
        f"{len(custom_company_sets['CUSTOM_EQUITY_HINT'])}**",
        f"- UNCLASSIFIED rows / companies: **{custom_counts['UNCLASSIFIED_rows']} / "
        f"{len(custom_any_unclassified)}**",
        f"- UNCLASSIFIED companies with passive-side hint: **{len(custom_passive_unclassified)}**",
        "",
        "## Closure feasibility",
        "",
        f"- LSE on BS face: **{len(lse_face)}**",
        f"- LSE usable annual + BS face: **{len(lse_usable)}**",
        "- Strict §7.2 closure demonstrated: **NOT COMPUTED**",
        "- Blocker: **PRE_HAS_ORDER_BUT_NO_PARENT_CHILD_OR_CALCULATION_HIERARCHY**",
        "",
        "## Invariant",
        "",
        "**T00-bis only. data/current untouched. No candidate. No ranking. No Blind Test.**",
        "",
    ]
    MD_PATH.write_text("\n".join(md), encoding="utf-8")

    end_sha = sha256_file(FUNDAMENTALS_PATH)
    if end_sha != base_sha:
        raise SystemExit(
            "BASE_CHANGED_DURING_T00BIS: il canonico è cambiato durante il probe; "
            "evidenza non valida, rieseguire."
        )

    print("OK — BR04-T00-bis v1.2 completato.")
    print(f"base_canonical_sha256={base_sha}")
    print(f"evidence={JSON_PATH.relative_to(ROOT)}")
    print("data/current modified: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
