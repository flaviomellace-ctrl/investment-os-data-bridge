#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import bridge

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "current"
FUNDAMENTALS_PATH = DATA_DIR / "sp500_fundamentals.csv"
JSON_PATH = DATA_DIR / "br04_t00_report.json"
MD_PATH = DATA_DIR / "br04_t00_report.md"

SEC_QUARTERS = 16
SCHEMA = "br04_t00_probe_v1.0"

TAG_GROUPS = {
    "current_debt": [
        "LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper",
        "LinesOfCreditCurrent", "NotesPayableCurrent", "SecuredDebtCurrent",
        "UnsecuredDebtCurrent", "ConvertibleNotesPayableCurrent",
        "OtherShortTermBorrowings", "FinanceLeaseLiabilityCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent", "DebtCurrent",
    ],
    "noncurrent_debt": [
        "LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations",
        "LongTermNotesPayable", "SeniorLongTermNotes",
        "ConvertibleLongTermNotesPayable", "LongTermLineOfCredit",
        "OtherLongTermDebtNoncurrent", "SecuredLongTermDebt",
        "UnsecuredLongTermDebt", "SecuredDebt", "UnsecuredDebt",
        "NotesPayable", "FinanceLeaseLiabilityNoncurrent",
    ],
    "debt_aggregates": [
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
        "DebtAndCapitalLeaseObligations",
        "DebtLongtermAndShorttermCombinedAmount",
        "FinanceLeaseLiability",
    ],
    "interest": [
        "InterestExpense", "InterestExpenseNonoperating",
        "InterestExpenseDebt", "InterestAndDebtExpense", "InterestPaidNet",
        "InterestIncomeExpenseNet", "InterestIncomeExpenseNonoperatingNet",
        "InterestRevenueExpenseNet", "InvestmentIncomeInterest",
    ],
    "cash_sti_leases_controls": [
        "CashAndCashEquivalentsAtCarryingValue", "Cash",
        "ShortTermInvestments", "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "OperatingLeaseLiabilityCurrent",
        "OperatingLeaseLiabilityNoncurrent", "OperatingLeaseLiability",
        "Liabilities", "LiabilitiesAndStockholdersEquity",
        "StockholdersEquity",
    ],
    "legacy_bridge_debt_diagnostic": [
        "LongTermDebtAndFinanceLeaseObligations",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    ],
}
ALL_TAGS = sorted({t for tags in TAG_GROUPS.values() for t in tags})

CUSTOM_DEBT_LABEL_RE = re.compile(
    r"\b(debt|borrow(?:ing|ings)?|note(?:s)?|loan(?:s)?|credit\s+facilit(?:y|ies)|"
    r"commercial\s+paper|bond(?:s)?|finance\s+lease|term\s+loan)\b", re.I
)
CUSTOM_LIABILITY_LABEL_RE = re.compile(
    r"\b(liabilit(?:y|ies)|payable(?:s)?|obligation(?:s)?|debt|borrow(?:ing|ings)?|"
    r"note(?:s)?|loan(?:s)?|credit\s+facilit(?:y|ies)|commercial\s+paper|"
    r"bond(?:s)?|lease)\b", re.I
)

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def norm_text(v):
    if v is None or pd.isna(v):
        return ""
    return str(v).strip()

def read_tsv_member(zf, filename, **kwargs):
    names = {n.lower(): n for n in zf.namelist()}
    actual = names.get(filename.lower())
    if not actual:
        raise bridge.BridgeError(f"{filename} non presente nel dataset SEC")
    with zf.open(actual) as f:
        return pd.read_csv(f, sep="\t", dtype=str, low_memory=False, **kwargs)

def main():
    if not FUNDAMENTALS_PATH.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato")

    fundamentals = pd.read_csv(FUNDAMENTALS_PATH, low_memory=False)
    if "ticker" not in fundamentals.columns or "annual_adsh" not in fundamentals.columns:
        raise SystemExit("ticker/annual_adsh mancanti nel fundamentals")
    if fundamentals["ticker"].duplicated().any():
        raise SystemExit("Ticker duplicati nel fundamentals")

    annual_adshs = {
        norm_text(x)
        for x in fundamentals["annual_adsh"].dropna()
        if norm_text(x)
    }

    downloader = bridge.Downloader()
    quarters, _ = bridge.discover_sec_quarters(downloader)
    selected = quarters[-SEC_QUARTERS:]

    face_by_tag = defaultdict(set)
    num_by_tag = defaultdict(set)
    stmt_by_tag = defaultdict(lambda: defaultdict(set))
    custom_bs_companies = set()
    custom_liability_companies = set()
    custom_debt_companies = set()
    custom_bs_rows = custom_liability_rows = custom_debt_rows = 0

    with tempfile.TemporaryDirectory(prefix="investment_os_br04_t00_") as td:
        td = Path(td)
        for q in selected:
            path = td / f"{q.key}.zip"
            print(f"Scarico {q.label} ...")
            bridge.download_to_file(downloader, q.url, path)

            with zipfile.ZipFile(path) as zf:
                pre = read_tsv_member(
                    zf, "pre.txt",
                    usecols=lambda c: c in {"adsh","stmt","inpth","tag","version","plabel","line"}
                )
                pre = pre[pre["adsh"].isin(annual_adshs)].copy()
                pre["stmt"] = pre["stmt"].fillna("").str.upper().str.strip()
                pre["inpth"] = pd.to_numeric(pre["inpth"], errors="coerce")
                face = pre[
                    pre["stmt"].isin({"BS","IS","CF"}) &
                    pre["inpth"].fillna(0).eq(0)
                ].copy()

                rel = face[face["tag"].isin(ALL_TAGS)]
                for tag, grp in rel.groupby("tag"):
                    face_by_tag[tag].update(grp["adsh"].dropna().astype(str))
                    for stmt, sg in grp.groupby("stmt"):
                        stmt_by_tag[tag][stmt].update(sg["adsh"].dropna().astype(str))

                tagdf = read_tsv_member(
                    zf, "tag.txt",
                    usecols=lambda c: c in {"tag","version","custom"}
                )
                tagdf["custom"] = pd.to_numeric(tagdf["custom"], errors="coerce")
                custom_pairs = set(zip(
                    tagdf.loc[tagdf["custom"].eq(1), "tag"].fillna(""),
                    tagdf.loc[tagdf["custom"].eq(1), "version"].fillna("")
                ))

                bs = face[face["stmt"].eq("BS")].copy()
                if custom_pairs and not bs.empty:
                    pairs = list(zip(bs["tag"].fillna(""), bs["version"].fillna("")))
                    bs["_custom"] = [p in custom_pairs for p in pairs]
                    cbs = bs[bs["_custom"]]
                    custom_bs_rows += len(cbs)
                    custom_bs_companies.update(cbs["adsh"].dropna().astype(str))
                    labels = cbs["plabel"].fillna("")
                    liab = cbs[labels.str.contains(CUSTOM_LIABILITY_LABEL_RE, na=False)]
                    debt = cbs[labels.str.contains(CUSTOM_DEBT_LABEL_RE, na=False)]
                    custom_liability_rows += len(liab)
                    custom_debt_rows += len(debt)
                    custom_liability_companies.update(liab["adsh"].dropna().astype(str))
                    custom_debt_companies.update(debt["adsh"].dropna().astype(str))

                names = {n.lower(): n for n in zf.namelist()}
                actual = names.get("num.txt")
                if not actual:
                    raise bridge.BridgeError(f"num.txt non presente in {q.key}")
                with zf.open(actual) as f:
                    for chunk in pd.read_csv(
                        f, sep="\t", dtype=str, low_memory=False, chunksize=250_000
                    ):
                        mask = chunk["adsh"].isin(annual_adshs) & chunk["tag"].isin(ALL_TAGS)
                        if "coreg" in chunk.columns:
                            mask &= chunk["coreg"].fillna("").eq("")
                        if "segments" in chunk.columns:
                            mask &= chunk["segments"].fillna("").eq("")
                        part = chunk.loc[mask, ["adsh","tag"]]
                        for tag, grp in part.groupby("tag"):
                            num_by_tag[tag].update(grp["adsh"].dropna().astype(str))

    group_for_tag = {
        tag: group
        for group, tags in TAG_GROUPS.items()
        for tag in tags
    }

    tags_report = {}
    for tag in ALL_TAGS:
        face = face_by_tag[tag]
        num = num_by_tag[tag]
        tags_report[tag] = {
            "group": group_for_tag[tag],
            "face_statement_companies": len(face),
            "num_companies": len(num),
            "num_only_companies": len(num - face),
            "face_stmt_breakdown": {
                s: len(stmt_by_tag[tag][s]) for s in ("BS","IS","CF")
            },
        }

    groups = {}
    for group, tags in TAG_GROUPS.items():
        fu = set()
        nu = set()
        for tag in tags:
            fu |= face_by_tag[tag]
            nu |= num_by_tag[tag]
        groups[group] = {
            "face_statement_companies_any_tag": len(fu),
            "num_companies_any_tag": len(nu),
            "num_only_companies_any_tag": len(nu - fu),
        }

    report = {
        "schema": SCHEMA,
        "generated_at_utc": now_iso(),
        "purpose": "BR04-T00 census only; no canonical dataset modification",
        "universe_rows": len(fundamentals),
        "companies_with_annual_adsh": len(annual_adshs),
        "companies_without_annual_adsh": len(fundamentals) - len(annual_adshs),
        "quarters_used": [q.key for q in selected],
        "groups": groups,
        "tags": tags_report,
        "custom_face_statement_lines": {
            "custom_bs_face_rows": custom_bs_rows,
            "custom_bs_companies": len(custom_bs_companies),
            "custom_liability_face_rows": custom_liability_rows,
            "custom_liability_companies": len(custom_liability_companies),
            "custom_debt_face_rows": custom_debt_rows,
            "custom_debt_companies": len(custom_debt_companies),
        },
        "rules": [
            "Face statement = pre.txt stmt BS/IS/CF and inpth=0.",
            "NUM counts use consolidated/unsegmented facts when columns are available.",
            "num_only = annual filing fact in NUM but not on face statement.",
            "No ticker is written.",
            "No canonical fundamentals/coverage/status/manifest/chunks are modified.",
        ],
    }

    bridge.write_json_atomic(JSON_PATH, report)

    lines = [
        "# BR-04 T00 — Face-statement census",
        "",
        f"- Generated: **{report['generated_at_utc']}**",
        f"- Universe: **{report['universe_rows']}**",
        f"- Companies with annual ADSH: **{report['companies_with_annual_adsh']}**",
        f"- SEC quarters: **{len(report['quarters_used'])}** "
        f"({report['quarters_used'][0]} → {report['quarters_used'][-1]})",
        "- Canonical fundamentals modified: **NO**",
        "",
        "## Group summary",
        "",
        "| Group | Face | NUM | NUM-only |",
        "| --- | ---: | ---: | ---: |",
    ]
    for group, st in groups.items():
        lines.append(
            f"| `{group}` | {st['face_statement_companies_any_tag']} | "
            f"{st['num_companies_any_tag']} | {st['num_only_companies_any_tag']} |"
        )

    c = report["custom_face_statement_lines"]
    lines += [
        "",
        "## Custom BS lines",
        "",
        f"- Custom BS face rows: **{c['custom_bs_face_rows']}** across "
        f"**{c['custom_bs_companies']}** companies.",
        f"- Custom liability-like rows: **{c['custom_liability_face_rows']}** across "
        f"**{c['custom_liability_companies']}** companies.",
        f"- Custom debt-like rows: **{c['custom_debt_face_rows']}** across "
        f"**{c['custom_debt_companies']}** companies.",
        "",
        "## Tag census",
        "",
        "| Group | Tag | Face | NUM | NUM-only | BS | IS | CF |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for tag, st in tags_report.items():
        b = st["face_stmt_breakdown"]
        lines.append(
            f"| `{st['group']}` | `{tag}` | {st['face_statement_companies']} | "
            f"{st['num_companies']} | {st['num_only_companies']} | "
            f"{b['BS']} | {b['IS']} | {b['CF']} |"
        )
    lines += [
        "",
        "## Invariant",
        "",
        "**T00 only. No canonical dataset modification. No ranking. No Blind Test.**",
        "",
    ]
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("OK — BR04-T00 completato.")
    print("Canonical fundamentals modified: NO")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
