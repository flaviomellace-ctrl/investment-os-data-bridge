#!/usr/bin/env python3
"""Independent SEC re-read of revenue and operating-lease facts (research snapshot, read-only).

Source: SEC XBRL companyfacts API (https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json).
For each row of the input (ticker, cik, annual_adsh) it reads the USD facts reported IN THAT SAME
ACCESSION: total and contract revenue for the fiscal year (duration 350-380 days, latest end) and
operating lease liabilities (instant, latest end). Nothing is inferred: a fact absent from the
accession stays empty. Output is a separate snapshot; it never overwrites a candidate.
"""
from __future__ import annotations

import csv, hashlib, json, sys
from datetime import date, datetime
from pathlib import Path

import bridge

REV = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]
LEASE = ["OperatingLeaseLiability", "OperatingLeaseLiabilityCurrent", "OperatingLeaseLiabilityNoncurrent"]


def days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def read(facts: dict, tag: str, accn: str, duration: bool):
    xs = [f for f in ((facts.get(tag) or {}).get("units") or {}).get("USD", []) if f.get("accn") == accn]
    if duration:
        xs = [f for f in xs if f.get("start") and 350 <= days(f["start"], f["end"]) <= 380]
    else:
        xs = [f for f in xs if not f.get("start")]
    if not xs:
        return None, ""
    end = max(f["end"] for f in xs)
    vals = sorted({float(f["val"]) for f in xs if f["end"] == end})
    return (vals[-1] if duration else vals[0] if len(vals) == 1 else None), end


def main(inp: Path, out: Path) -> None:
    d = bridge.Downloader()
    rows = list(csv.DictReader(inp.open()))
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["ticker", "cik", "annual_adsh", "status"] + [f"sec_{t}" for t in REV] + ["sec_revenue_end"] + [f"sec_{t}" for t in LEASE] + ["sec_lease_end", "fetched_utc"]
    n = dict(ok=0, no_id=0, error=0)
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            o = dict(ticker=r["ticker"], cik=r["cik"], annual_adsh=r["annual_adsh"], fetched_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z")
            if not r["cik"] or not r["annual_adsh"]:
                o["status"] = "NO_IDENTIFIER"; n["no_id"] += 1; w.writerow(o); continue
            try:
                facts = d.get_sec(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{r['cik']}.json", timeout=90).json().get("facts", {}).get("us-gaap", {})
            except Exception as e:
                o["status"] = f"ERROR:{type(e).__name__}"; n["error"] += 1; w.writerow(o); continue
            ends = []
            for t in REV:
                v, e = read(facts, t, r["annual_adsh"], True)
                o[f"sec_{t}"] = "" if v is None else repr(v); ends.append(e)
            o["sec_revenue_end"] = max(ends) if any(ends) else ""
            ends = []
            for t in LEASE:
                v, e = read(facts, t, r["annual_adsh"], False)
                o[f"sec_{t}"] = "" if v is None else repr(v); ends.append(e)
            o["sec_lease_end"] = max(ends) if any(ends) else ""
            o["status"] = "OK"; n["ok"] += 1; w.writerow(o)
    meta = dict(schema="sec_reread_snapshot_v1", source="SEC XBRL companyfacts API", endpoint="https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                period="fiscal year of each row's annual accession", unit="USD", currency="USD", delay="as published by SEC at retrieval time",
                retrieved_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z", input=str(inp), input_sha256=hashlib.sha256(inp.read_bytes()).hexdigest(),
                rows=len(rows), counts=n, output_sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1))
    print("SEC_REREAD=" + json.dumps(meta["counts"]))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
