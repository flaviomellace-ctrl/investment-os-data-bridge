#!/usr/bin/env python3
"""Evidence collection only. Does not clear gates or modify frozen economics."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
import r10d_real_overlays as base

ROOT = Path(__file__).resolve().parents[1]
R10D = ROOT / "data/v4_2/r10d/36303846263"
INPUT_HASHES = {
    "V4_2_R10D_DEEP_DIVE_QUEUE.csv": "6f98eb035083ab13830fa77058278cfdc14bd424de21a74bb839a1c3edc5e645",
    "V4_2_R10D_REAL_OVERLAYS.csv": "922210ba7b49f3c17b5a761d1a72038edccb6005751ffafdab91aa3a03fce121",
}
CASH_SHA = "1d76a9a260793614edb5964b02eaed71b8b0ce6307fdb257d16773b9adb1ef3a"
TERMS = {
    "working_capital": base.CASH_WC_TERMS,
    "tax_timing": base.CASH_TAX_TERMS,
    "reserve_float": base.CASH_RESERVE_TERMS,
    "noncash_revaluation": base.CASH_REVAL_TERMS,
    "purchase_obligations": base.PURCHASE_TERMS,
    "guarantees": base.GUARANTEE_TERMS,
    "off_balance": base.OFFBAL_TERMS,
    "take_or_pay": ["take-or-pay", "take or pay", "offtake", "off-take"],
    "capacity_content_fleet": ["capacity commitments", "content commitments", "fleet commitments"],
    "leases": ["operating lease", "finance lease"],
    "agency_net": base.AGENCY_NET_TERMS,
    "two_sided": base.TWO_SIDED_TERMS,
    "volume": base.VOLUME_TERMS,
}
FACT_PATTERN = re.compile(r"depreciation|amortization|depletion|operatingincomeloss|costofrevenue|costofgoods|debt|lease|cashandcash|purchase.*obligation|unconditionalpurchase|guarantee", re.I)


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def exact_annual_fact(cf, concepts, accession, period):
    """No latest-filing or quarterly fallback; conflicting same-priority facts stop selection."""
    for taxonomy, concept, unit in concepts:
        accepted = []
        for fact in cf.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("accn") != accession or fact.get("end") != period:
                continue
            if fact.get("form") not in base.ANNUAL_FORMS or finite(fact.get("val")) is None:
                continue
            try:
                duration = (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
            except (KeyError, ValueError, TypeError):
                continue
            if 330 <= duration <= 380:
                accepted.append(dict(fact, taxonomy=taxonomy, concept=concept, unit=unit, duration_days=duration))
        if accepted:
            if len({float(f["val"]) for f in accepted}) > 1:
                return {"status": "CONFLICTING", "facts": accepted, "value": None}
            return {"status": "PRESENT", "facts": accepted, "value": float(accepted[0]["val"])}
    return {"status": "MISSING", "facts": [], "value": None}


def contexts(text):
    result = {}
    for category, terms in TERMS.items():
        matches = []
        for term in terms:
            for match in re.finditer(re.escape(term), text):
                start, end = max(0, match.start() - 500), min(len(text), match.end() + 900)
                matches.append({"term": term, "offset": match.start(), "excerpt_start": start,
                                "excerpt_end": end, "text": text[start:end]})
        result[category] = {"match_count": len(matches), "status": "REVIEW_REQUIRED" if matches else "NOT_ESTABLISHED",
                            "matches": matches[:30], "truncated": len(matches) > 30}
    return result


def filing_by_accession(sub, accession, cik):
    recent = sub.get("filings", {}).get("recent", {})
    for i, acc in enumerate(recent.get("accessionNumber", [])):
        if acc == accession:
            doc = recent["primaryDocument"][i]
            return {"accession": acc, "report_date": recent["reportDate"][i],
                    "filed": recent["filingDate"][i], "form": recent["form"][i],
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"}
    raise ValueError("PINNED_ACCESSION_NOT_IN_RECENT_SUBMISSIONS")


def candidate_facts(cf, accession):
    result = []
    for tax, concepts in cf.get("facts", {}).items():
        for concept, spec in concepts.items():
            if not FACT_PATTERN.search(concept):
                continue
            for unit, facts in spec.get("units", {}).items():
                for fact in facts:
                    if fact.get("accn") == accession:
                        result.append(dict(fact, taxonomy=tax, concept=concept, unit=unit))
    return result


def main():
    run = os.environ["GITHUB_RUN_ID"]
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    output = ROOT / "data/v4_2/r10e" / f"{run}-{attempt}"
    if output.exists():
        raise SystemExit("Output already exists; immutable evidence cannot be overwritten")
    checks = {name: base.sha(R10D / name) == expected for name, expected in INPUT_HASHES.items()}
    checks.update(candidate=base.sha(base.CAND) == base.CAND_SHA,
                  frozen_cash_module=base.sha(base.CASH) == CASH_SHA)
    if not all(checks.values()):
        raise SystemExit("Frozen input seal mismatch: " + json.dumps(checks))
    before = {str(p.relative_to(ROOT)): base.sha(p) for p in (ROOT / "src").glob("*.py")}
    email = os.environ.get("SEC_CONTACT_EMAIL", "").strip()
    if "@" not in email:
        raise SystemExit("SEC_CONTACT_EMAIL required")
    output.mkdir(parents=True)
    raw_dir = Path(os.environ["RUNNER_TEMP"]) / "r10e_primary_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)
    queue = base.rows(R10D / "V4_2_R10D_DEEP_DIVE_QUEUE.csv")
    overlays = {r["ticker"]: r for r in base.rows(R10D / "V4_2_R10D_REAL_OVERLAYS.csv")}
    candidates = {r["ticker"]: r for r in base.rows(base.CAND)}
    if len(queue) != 10 or len({r["ticker"] for r in queue}) != 10 or set(overlays) != {r["ticker"] for r in queue}:
        raise SystemExit("Queue cardinality or identity mismatch")
    summaries, errors = [], []
    last = [0.0]
    for q in queue:
        ticker = q["ticker"]
        if not re.fullmatch(r"[A-Za-z0-9.\-]+", ticker):
            raise SystemExit("Unsafe entity filename")
        c, old = candidates[ticker], overlays[ticker]
        cik = base.cik10(c["cik"])
        accession, period = c["annual_adsh"], base.norm_period(c["annual_period"])
        try:
            cf_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            cf_raw = base.fetch_bytes(cf_url, email, last)
            sub_raw = base.fetch_bytes(sub_url, email, last)
            cf, sub = json.loads(cf_raw), json.loads(sub_raw)
            (raw_dir / f"{ticker}_companyfacts.json").write_bytes(cf_raw)
            (raw_dir / f"{ticker}_submissions.json").write_bytes(sub_raw)
            filings = {}
            for acc in dict.fromkeys([accession, old["filing_accession"]]):
                filing = filing_by_accession(sub, acc, cik)
                raw = base.fetch_bytes(filing["url"], email, last)
                digest = hashlib.sha256(raw).hexdigest()
                if acc == old["filing_accession"] and digest != old["filing_sha256"]:
                    raise ValueError("R10D_PRIMARY_FILING_HASH_MISMATCH")
                (raw_dir / f"{ticker}_{acc}.html").write_bytes(raw)
                filings[acc] = dict(filing, sha256=digest, contexts=contexts(base.html_to_text(raw)))
            actual_period = filings[accession]["report_date"]
            da_frozen = exact_annual_fact(cf, base.DA_CONCEPTS, accession, period)
            da_actual = exact_annual_fact(cf, base.DA_CONCEPTS, accession, actual_period)
            missing = [field for field in ["annual_operating_income", "total_debt", "cash_and_equivalents", "annual_sbc"] if base.num(c.get(field)) is None]
            if da_frozen["status"] != "PRESENT":
                missing.append("annual_DA_exact_frozen_period")
            issues = ["SEMANTIC_CASH_AND_COMMITMENTS_RECONCILIATION_OPEN", "NORMALIZATION_NOT_COMPLETE"]
            if period != actual_period:
                issues.append("CANDIDATE_PERIOD_DIFFERS_FROM_SAME_ACCESSION_REPORT_DATE")
            if accession != old["filing_accession"]:
                issues.append("R10D_OVERLAY_USES_DIFFERENT_FILING_FROM_FROZEN_FUNDAMENTALS")
            if c.get("total_debt_status") != "PRESENT":
                issues.append("DEBT_" + (c.get("total_debt_status") or "UNKNOWN"))
            record = {
                "ticker": ticker, "queue": q, "frozen_candidate_period": period,
                "frozen_candidate_accession": accession, "same_accession_report_date": actual_period,
                "prior_overlay": old, "filings": filings,
                "companyfacts_source": {"url": cf_url, "sha256": hashlib.sha256(cf_raw).hexdigest()},
                "submissions_source": {"url": sub_url, "sha256": hashlib.sha256(sub_raw).hexdigest()},
                "frozen_candidate_row": c,
                "DA_at_frozen_period": da_frozen,
                "DA_at_report_date_review_only": da_actual,
                "same_accession_fact_inventory_review_only": candidate_facts(cf, accession),
                "missing_leverage_inputs": missing, "open_issues": issues,
                "resolution_status": "OPEN", "normalized_owner_earnings": None,
                "ranking_recomputed": False, "system_live": False,
            }
            write_json(output / f"{ticker}_EVIDENCE.json", record)
            summaries.append({"ticker": ticker, "missing": missing, "issues": issues,
                              "DA_frozen": da_frozen["status"], "DA_report_date": da_actual["status"],
                              "cash_gate": old["cash_quality_gate"], "commitments_gate": old["commitments_gate"],
                              "prior_leverage_status": old["leverage_status"]})
        except Exception as exc:
            errors.append({"ticker": ticker, "error_type": type(exc).__name__})
    after = {str(p.relative_to(ROOT)): base.sha(p) for p in (ROOT / "src").glob("*.py")}
    if before != after:
        raise SystemExit("Source mutation detected")
    report = ["# V4.2 R10E — Reconciliation evidence", "", "Evidence collection only; all substantive cases remain OPEN. System NOT LIVE.", "",
              "| Entity | Missing frozen leverage inputs | Additional integrity issues |", "|---|---|---|"]
    for s in summaries:
        report.append(f"| {s['ticker']} | {', '.join(s['missing']) or 'None; debt completeness still requires review'} | {', '.join(s['issues'][2:]) or 'None detected'} |")
    report += ["", "## Interpretation", "", "- A lexical match is a review lead; it does not establish materiality, direction, amount or negation.",
               "- No match is NOT_ESTABLISHED, not a verified negative. Contexts may be truncated; inspect the full primary document.",
               "- Zero quantified commitments in R10D is not proof of zero obligations.",
               "- PARTIAL debt is not promoted to a complete leverage measure.",
               "- Facts at the actual report date are review proposals only; no frozen input, score, threshold, queue or gate is overwritten.",
               "- Annual facts must match accession, end date, unit and a 330–380-day duration. Conflicting values remain CONFLICTING.",
               "- Current Companyfacts retrieval is new evidence. It is not represented as a historical point-in-time archive.",
               "- Full downloaded primary sources are preserved in the workflow artifact; repository dossiers retain hashes, source URLs, contexts and fact provenance.",
               "", "## Remaining required gates", "", "1. Document and reconcile cash, commitments, leases/debt overlap and missing inputs.",
               "2. R11: use separately sealed non-current controls with pre-registered scoring.",
               "3. R12: clean-room executor receives only frozen artifacts and safe methodology, not this conversation or target validation.",
               "4. Bootstrap/IPS only after the existing regression plan's acceptance criteria are satisfied.",
               "", "A successful workflow means evidence collection completed, not validation passed or project 100% complete."]
    (output / "V4_2_R10E_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    write_json(output / "V4_2_R10E_SUMMARY.json", {"cases": summaries, "errors": errors})
    receipt = {"schema": "investment_os_r10e_evidence_v1", "run_id": run, "attempt": attempt,
               "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
               "collection_complete": len(summaries) == 10 and not errors, "resolved_cases": 0,
               "system_live": False, "engine_modified": False, "ranking_recomputed": False,
               "source_sha256": before, "outputs": {p.name: base.sha(p) for p in output.iterdir()},
               "next_gate": "SEMANTIC_RECONCILIATION_THEN_R11_THEN_INDEPENDENT_R12"}
    write_json(output / "V4_2_R10E_RECEIPT.json", receipt)
    print(json.dumps({"collection_complete": receipt["collection_complete"], "case_count": len(summaries), "resolved_cases": 0, "errors": errors, "system_live": False}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
