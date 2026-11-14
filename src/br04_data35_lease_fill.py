#!/usr/bin/env python3
"""DATA35 (research, not promoted) = DATA34 + operating lease liabilities read from the SEC re-read snapshot.

Only `operating_lease_liabilities` changes, and only where it was empty and the SEC companyfacts fact
belongs to the same annual accession and the same balance-sheet date. Revenue differences found by the
same snapshot are NOT written into the candidate: they are added to the evidence file as open
data conflicts, which block the affected rows in the integrated pipeline.
Usage: br04_data35_lease_fill.py DATA34.csv sec_reread.csv evidence_DATA34.json OUT_DIR
"""
import hashlib, json, sys
from pathlib import Path

import pandas as pd


def num(v):
    return float(v) if v not in ("", None) else None


def main(src: Path, snap: Path, evidence: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(src, dtype=str, keep_default_na=False)
    s = pd.read_csv(snap, dtype=str, keep_default_na=False).set_index("ticker")
    filled, skipped, conf = [], [], []
    for i, r in d.iterrows():
        t = r["ticker"]
        if t not in s.index:
            continue
        x = s.loc[t]
        if x["annual_adsh"] != r["annual_adsh"] or x["status"] != "OK":
            continue
        tot, c, n = (num(x[f"sec_OperatingLeaseLiability{k}"]) for k in ("", "Current", "Noncurrent"))
        val = tot if tot is not None else (c + n if c is not None and n is not None else None)
        if r["operating_lease_liabilities"] == "" and val is not None:
            bal, end = r["total_liabilities_and_equity_ddate"].split(".")[0], x["sec_lease_end"].replace("-", "")
            if bal and bal == end:
                d.at[i, "operating_lease_liabilities"] = repr(val)
                filled.append(dict(ticker=t, value=val, end=x["sec_lease_end"], accn=r["annual_adsh"], basis="aggregate" if tot is not None else "current+noncurrent"))
            else:
                skipped.append(dict(ticker=t, balance=bal, lease_end=end))
        rev, st = num(r["annual_revenue"]), num(x["sec_Revenues"])
        if rev and st and r["annual_revenue_tag"].startswith("RevenueFromContract") and st > rev * 1.005:
            conf.append(dict(ticker=t, candidate=rev, primary=st, accn=r["annual_adsh"]))
    out = out_dir / "DATA35_RESEARCH_NOT_PROMOTED.csv"
    d.to_csv(out, index=False, lineterminator="\r\n")
    a = pd.read_csv(src, dtype=str, keep_default_na=False)
    changed = [c for c in a.columns if not a[c].equals(d[c])]
    assert changed == ["operating_lease_liabilities"], changed
    ev = json.loads(evidence.read_text())
    snap_sha = hashlib.sha256(snap.read_bytes()).hexdigest()
    source = f"SEC XBRL companyfacts, same annual accession, re-read snapshot sha256 {snap_sha}"
    added = 0
    for c in conf:
        lst = ev["entities"].setdefault(c["ticker"], {}).setdefault("data_conflicts", [])
        if not any(z.get("field") == "annual_revenue" for z in lst):
            lst.append(dict(field="annual_revenue", candidate_value=c["candidate"], primary_value=c["primary"], unit="USD", status="OPEN",
                            source=source + " accession " + c["accn"], note="candidate equals contract-revenue tag; us-gaap:Revenues in the same filing is larger"))
            added += 1
    ev["evidence_set_id"] = "DATA35-EVIDENCE-v1"
    ev["note"] = (ev.get("note", "") + " | DATA35: revenue conflicts extended from the full SEC re-read of the annual accessions.").strip(" |")
    (out_dir / "evidence_DATA35_v1.json").write_text(json.dumps(ev, indent=1, sort_keys=True))
    rep = dict(schema="data35_report_v1", status="RESEARCH_NOT_PROMOTED", base="DATA34", base_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
               sha256=hashlib.sha256(out.read_bytes()).hexdigest(), rows=len(d), cols=len(d.columns), snapshot_sha256=snap_sha,
               change="operating_lease_liabilities filled where missing (same accession, same balance date); no other column changed",
               lease_present_before=int((a.operating_lease_liabilities != "").sum()), lease_present_after=int((d.operating_lease_liabilities != "").sum()),
               filled=len(filled), skipped_balance_date_mismatch=skipped, revenue_conflicts_added=added,
               revenue_conflicts_total=sum(1 for v in ev["entities"].values() if any(z.get("field") == "annual_revenue" for z in v.get("data_conflicts", []))),
               filled_rows=filled)
    (out_dir / "data35_report.json").write_text(json.dumps(rep, indent=1))
    print("DATA35=" + json.dumps({k: rep[k] for k in ("sha256", "lease_present_before", "lease_present_after", "filled", "revenue_conflicts_total")}))


if __name__ == "__main__":
    main(*(Path(p) for p in sys.argv[1:5]))
