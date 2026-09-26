#!/usr/bin/env python3
"""
Investment OS V4.2 — R10B primary-source recovery candidate.

This is a DATA-LAYER recovery step only.
It reads the frozen V4.1 canonical and the frozen R10A source-recovery queue,
queries SEC Companyfacts with a declared User-Agent, and writes a separate
V4.2 candidate dataset. It never modifies data/current and never runs BQS/IOS.

Rules:
- no ticker whitelist;
- no fuzzy concept matching;
- only pre-registered economically equivalent XBRL concepts;
- exact fiscal-period end matching;
- annual forms only;
- annual-duration facts only for flow/share metrics;
- existing canonical values are never overwritten;
- MISSING stays MISSING when no admissible primary fact exists;
- every recovered value gets provenance.
"""

from __future__ import annotations
import csv, hashlib, json, math, os, time, urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT=Path(__file__).resolve().parents[1]
CANON=ROOT/"data/current/sp500_fundamentals.csv"
R10A=ROOT/"data/v4_2/r10a/36265062577"
QUEUE=R10A/"V4_2_R10A_SOURCE_RECOVERY_QUEUE.csv"
R10A_RECEIPT=R10A/"V4_2_R10A_RECEIPT.json"
ENGINE_MANIFEST=ROOT/"docs/V4_2_ENGINE_MANIFEST.json"

CANON_SHA="d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45"
QUEUE_SHA="4a6c40cd0ae0af8d6b6b5d2b7c1143fdc417d3f7a579f0e2fa70ed7135e7e084"
ENGINE_SHA="cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e"

SEC_MIN_SECONDS=0.35
ANNUAL_FORMS={"10-K","20-F","40-F"}

# Pre-registered concept allowlist. No fuzzy/ticker-specific concept discovery.
# Each tuple is (taxonomy, concept, expected unit family).
CONCEPTS={
 "revenue":[
   ("us-gaap","RevenueFromContractWithCustomerExcludingAssessedTax","USD"),
   ("us-gaap","RevenueFromContractWithCustomerIncludingAssessedTax","USD"),
   ("us-gaap","Revenues","USD"),
   ("us-gaap","SalesRevenueNet","USD"),
   ("us-gaap","SalesRevenueGoodsNet","USD"),
   ("us-gaap","SalesRevenueServicesNet","USD"),
 ],
 "operating_cash_flow":[
   ("us-gaap","NetCashProvidedByUsedInOperatingActivities","USD"),
 ],
 "capex":[
   ("us-gaap","PaymentsToAcquirePropertyPlantAndEquipment","USD"),
   ("us-gaap","PaymentsForAdditionsToPropertyPlantAndEquipment","USD"),
   ("us-gaap","PaymentsToAcquireProductiveAssets","USD"),
 ],
 "diluted_shares":[
   ("us-gaap","WeightedAverageNumberOfDilutedSharesOutstanding","shares"),
 ],
 "sbc":[
   ("us-gaap","ShareBasedCompensation","USD"),
   ("us-gaap","AllocatedShareBasedCompensationExpense","USD"),
   ("us-gaap","ShareBasedCompensationArrangementByShareBasedPaymentAwardCompensationCost","USD"),
   ("us-gaap","EmployeeServiceShareBasedCompensationAllocationOfRecognizedPeriodCostsCapitalizedAmount","USD"),
 ],
}

# Candidate fields that may be filled from primary SEC facts.
TARGETS=[
 ("annual_revenue","revenue","annual_period"),
 ("fy_minus_3_revenue","revenue","fy_minus_3_period"),
 ("annual_operating_cash_flow","operating_cash_flow","annual_period"),
 ("fy_minus_3_operating_cash_flow","operating_cash_flow","fy_minus_3_period"),
 ("annual_capex","capex","annual_period"),
 ("fy_minus_3_capex","capex","fy_minus_3_period"),
 ("annual_diluted_shares","diluted_shares","annual_period"),
 ("prior_diluted_shares","diluted_shares","fy_minus_1_period"),
 ("fy_minus_3_diluted_shares","diluted_shares","fy_minus_3_period"),
 ("annual_sbc","sbc","annual_period"),
]

def sha(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def read_csv(p:Path)->List[Dict[str,str]]:
    with p.open("r",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def write_csv(p:Path,rs:Sequence[Dict[str,Any]],fields:Sequence[str]):
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(fields),extrasaction="ignore");w.writeheader()
        for r in rs:w.writerow({k:r.get(k,"") for k in fields})

def num(v:Any)->Optional[float]:
    s=str(v or "").strip()
    if s in ("","nan","None","MISSING","NA","NOT_APPLICABLE","CONFLICTING"):return None
    try:x=float(s)
    except:return None
    return x if math.isfinite(x) else None

def norm_period(v:Any)->str:
    s="".join(ch for ch in str(v or "") if ch.isdigit())
    if len(s)!=8:return ""
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"

def cik10(v:Any)->str:
    s=str(v or "").strip()
    try:return str(int(float(s))).zfill(10)
    except:
        d="".join(ch for ch in s if ch.isdigit())
        return d.zfill(10) if d else ""

def days_between(start:str,end:str)->Optional[int]:
    try:
        a=date.fromisoformat(start);b=date.fromisoformat(end);return (b-a).days
    except:return None

def companyfacts_url(cik:str)->str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

def fetch_companyfacts(cik:str,email:str,last_request:[float])->dict:
    elapsed=time.monotonic()-last_request[0]
    if elapsed<SEC_MIN_SECONDS:time.sleep(SEC_MIN_SECONDS-elapsed)
    req=urllib.request.Request(companyfacts_url(cik),headers={
        "User-Agent":f"InvestmentOSDataBridge/1.0 {email}",
        "Accept-Encoding":"gzip, deflate",
        "Accept":"application/json",
    })
    with urllib.request.urlopen(req,timeout=45) as r:
        raw=r.read()
    last_request[0]=time.monotonic()
    return json.loads(raw.decode("utf-8"))

def choose_fact(cf:dict,metric:str,target_end:str)->Optional[Dict[str,Any]]:
    """Exact-period, annual-form, annual-duration, pre-registered-concept selector."""
    if not target_end:return None
    facts=cf.get("facts",{})
    for taxonomy,concept,unit in CONCEPTS[metric]:
        node=facts.get(taxonomy,{}).get(concept)
        if not node:continue
        units=node.get("units",{})
        # Companyfacts may spell shares as "shares"; USD is exact.
        vals=units.get(unit,[])
        candidates=[]
        for x in vals:
            if str(x.get("form","")).upper() not in ANNUAL_FORMS:continue
            if x.get("end")!=target_end:continue
            if "start" not in x:continue
            dur=days_between(x.get("start",""),x.get("end",""))
            # Reject quarterly/YTD-short and implausibly long spans.
            if dur is None or dur<250 or dur>450:continue
            val=x.get("val")
            try:val=float(val)
            except:continue
            if not math.isfinite(val):continue
            candidates.append((str(x.get("filed","")),str(x.get("accn","")),val,x,dur))
        if candidates:
            candidates.sort(key=lambda z:(z[0],z[1]),reverse=True)
            _,_,val,x,dur=candidates[0]
            return {
              "value":val,"taxonomy":taxonomy,"concept":concept,"unit":unit,
              "start":x.get("start",""),"end":x.get("end",""),"filed":x.get("filed",""),
              "form":x.get("form",""),"accn":x.get("accn",""),"duration_days":dur,
            }
    return None

def cagr3(cur,old):
    if cur is None or old is None or cur<=0 or old<=0:return None
    return (cur/old)**(1/3)-1

def fcf(ocf,capex):
    if ocf is None or capex is None:return None
    return ocf-abs(capex)

def per_share(v,s):
    if v is None or s is None or s<=0:return None
    return v/s

def derive_candidate(r:Dict[str,Any])->List[str]:
    changed=[]
    def set_if_missing(k,val):
        if num(r.get(k)) is None and val is not None:
            r[k]=val;changed.append(k)
    cur_rev=num(r.get("annual_revenue")); old_rev=num(r.get("fy_minus_3_revenue"))
    set_if_missing("revenue_cagr3",cagr3(cur_rev,old_rev))
    cursh=num(r.get("annual_diluted_shares")); prsh=num(r.get("prior_diluted_shares"))
    if num(r.get("diluted_shares_yoy")) is None and cursh is not None and prsh not in (None,0):
        r["diluted_shares_yoy"]=cursh/prsh-1;changed.append("diluted_shares_yoy")
    curfps=per_share(fcf(num(r.get("annual_operating_cash_flow")),num(r.get("annual_capex"))),cursh)
    oldfps=per_share(fcf(num(r.get("fy_minus_3_operating_cash_flow")),num(r.get("fy_minus_3_capex"))),
                     num(r.get("fy_minus_3_diluted_shares")))
    set_if_missing("fcf_per_share_cagr3",cagr3(curfps,oldfps))
    set_if_missing("fcf_cagr3",cagr3(
        fcf(num(r.get("annual_operating_cash_flow")),num(r.get("annual_capex"))),
        fcf(num(r.get("fy_minus_3_operating_cash_flow")),num(r.get("fy_minus_3_capex")))
    ))
    if num(r.get("annual_fcf")) is None:
        v=fcf(num(r.get("annual_operating_cash_flow")),num(r.get("annual_capex")))
        if v is not None:r["annual_fcf"]=v;changed.append("annual_fcf")
    if num(r.get("sbc_to_revenue")) is None:
        sbc=num(r.get("annual_sbc"));rev=num(r.get("annual_revenue"))
        if sbc is not None and rev not in (None,0):
            r["sbc_to_revenue"]=sbc/rev;changed.append("sbc_to_revenue")
    return changed

def main()->int:
    run=os.getenv("GITHUB_RUN_ID","LOCAL")
    out=ROOT/"data/v4_2/r10b"/run;out.mkdir(parents=True,exist_ok=True)
    for p in [CANON,QUEUE,R10A_RECEIPT,ENGINE_MANIFEST]:
        if not p.exists():raise SystemExit(f"missing {p}")
    rec=json.loads(R10A_RECEIPT.read_text());man=json.loads(ENGINE_MANIFEST.read_text())
    checks={
      "canonical_sha":sha(CANON)==CANON_SHA,
      "r10a_queue_sha":sha(QUEUE)==QUEUE_SHA,
      "r10a_frozen":rec.get("frozen") is True,
      "r10a_requires_source_recovery":"PRIMARY_SOURCE_RECOVERY_REQUIRED" in rec.get("decision_flags",[]),
      "engine_frozen":man.get("frozen") is True,
      "engine_sha":man.get("v4_2_engine_sha256")==ENGINE_SHA,
    }
    if not all(checks.values()):raise SystemExit("seal fail: "+",".join(k for k,v in checks.items() if not v))
    email=os.getenv("SEC_CONTACT_EMAIL","").strip()
    if "@" not in email:raise SystemExit("SEC_CONTACT_EMAIL GitHub Actions secret required")

    canonical=read_csv(CANON);fields=list(canonical[0].keys())
    by={r["ticker"].strip():dict(r) for r in canonical}
    q=read_csv(QUEUE);tickers=sorted({r["ticker"].strip() for r in q})
    last=[0.0];prov=[];unresolved=[];fetch_fail=[];rows_touched=set();direct_fills=Counter();derived_fills=Counter()

    for idx,ticker in enumerate(tickers,1):
        r=by.get(ticker)
        if r is None:
            unresolved.append({"ticker":ticker,"field":"*","reason":"TICKER_NOT_IN_CANONICAL"});continue
        cik=cik10(r.get("cik"))
        if not cik:
            unresolved.append({"ticker":ticker,"field":"*","reason":"CIK_MISSING"});continue
        try:cf=fetch_companyfacts(cik,email,last)
        except Exception as e:
            fetch_fail.append({"ticker":ticker,"cik":cik,"error":type(e).__name__})
            continue
        for field,metric,period_field in TARGETS:
            if num(r.get(field)) is not None:continue
            target=norm_period(r.get(period_field))
            if not target:
                unresolved.append({"ticker":ticker,"field":field,"reason":"TARGET_PERIOD_MISSING"});continue
            fact=choose_fact(cf,metric,target)
            if fact is None:
                unresolved.append({"ticker":ticker,"field":field,"reason":"NO_ADMISSIBLE_PREREGISTERED_COMPANYFACT"})
                continue
            r[field]=fact["value"];rows_touched.add(ticker);direct_fills[field]+=1
            prov.append({
              "ticker":ticker,"cik":cik,"field":field,"value":fact["value"],
              "source_url":companyfacts_url(cik),"taxonomy":fact["taxonomy"],"concept":fact["concept"],
              "unit":fact["unit"],"start":fact["start"],"end":fact["end"],"filed":fact["filed"],
              "form":fact["form"],"accession":fact["accn"],"duration_days":fact["duration_days"],
              "rule":"EXACT_PERIOD_ANNUAL_FORM_ANNUAL_DURATION_PREREGISTERED_CONCEPT",
            })
        before={k:r.get(k) for k in ["revenue_cagr3","diluted_shares_yoy","fcf_per_share_cagr3","fcf_cagr3","annual_fcf","sbc_to_revenue"]}
        changed=derive_candidate(r)
        if changed:rows_touched.add(ticker)
        for k in changed:
            derived_fills[k]+=1
            prov.append({
              "ticker":ticker,"cik":cik,"field":k,"value":r.get(k),
              "source_url":"","taxonomy":"","concept":"","unit":"","start":"","end":"","filed":"",
              "form":"","accession":"","duration_days":"",
              "rule":"DETERMINISTIC_DERIVATION_FROM_CANDIDATE_PRIMARY_FACTS",
            })
        if idx%25==0:print("processed",idx,"of",len(tickers))

    # Preserve original column order; recovery fills only existing canonical columns.
    candidate=[by[r["ticker"].strip()] for r in canonical]
    candidate_path=out/"V4_2_R10B_CANDIDATE_FUNDAMENTALS.csv"
    write_csv(candidate_path,candidate,fields)

    prov_fields=["ticker","cik","field","value","source_url","taxonomy","concept","unit","start","end","filed","form","accession","duration_days","rule"]
    write_csv(out/"V4_2_R10B_RECOVERY_PROVENANCE.csv",prov,prov_fields)
    write_csv(out/"V4_2_R10B_UNRESOLVED.csv",unresolved,["ticker","field","reason"])
    write_csv(out/"V4_2_R10B_FETCH_FAILURES.csv",fetch_fail,["ticker","cik","error"])

    # Original canonical must be unchanged after all network work.
    if sha(CANON)!=CANON_SHA:raise SystemExit("data/current canonical changed unexpectedly")

    agg={
      "schema":"investment_os_v4_2_r10b_aggregates_v1.0","run_id":run,"system_live":False,
      "engine_modified":False,"ranking_recomputed":False,"data_current_modified":False,
      "source":"SEC_COMPANYFACTS_PRIMARY","source_queue_rows":len(tickers),
      "rows_touched":len(rows_touched),"direct_primary_fills":sum(direct_fills.values()),
      "direct_fills_by_field":dict(sorted(direct_fills.items())),
      "derived_fills":sum(derived_fills.values()),"derived_fills_by_field":dict(sorted(derived_fills.items())),
      "provenance_rows":len(prov),"unresolved_items":len(unresolved),"fetch_failures":len(fetch_fail),
      "candidate_sha256":sha(candidate_path),
      "canonical_sha256_after_run":sha(CANON),
    }
    (out/"V4_2_R10B_AGGREGATES.json").write_text(json.dumps(agg,indent=2)+"\n")
    report=f"""# V4.2 R10B — Primary-source recovery candidate

- Source: **SEC Companyfacts**
- Queue companies: **{len(tickers)}**
- Rows touched: **{len(rows_touched)}**
- Direct primary facts recovered: **{sum(direct_fills.values())}**
- Deterministic derived fields recovered: **{sum(derived_fills.values())}**
- Unresolved items: **{len(unresolved)}**
- Fetch failures: **{len(fetch_fail)}**
- Candidate SHA-256: `{sha(candidate_path)}`
- Canonical SHA-256 after run: `{sha(CANON)}`

No engine rule was changed. No ranking was recomputed. `data/current` was not modified.

The candidate is not authorized for investment use until R10C reruns the same frozen V4.2 engine
and the recovery/provenance checks pass.

**System remains NOT LIVE.**
"""
    (out/"V4_2_R10B_REPORT.md").write_text(report)
    outs=["V4_2_R10B_CANDIDATE_FUNDAMENTALS.csv","V4_2_R10B_RECOVERY_PROVENANCE.csv",
          "V4_2_R10B_UNRESOLVED.csv","V4_2_R10B_FETCH_FAILURES.csv","V4_2_R10B_AGGREGATES.json","V4_2_R10B_REPORT.md"]
    receipt={
      "schema":"investment_os_v4_2_r10b_receipt_v1.0","stage":"R10B_PRIMARY_SOURCE_RECOVERY_CANDIDATE",
      "run_id":run,"frozen":True,"system_live":False,"engine_modified":False,"ranking_recomputed":False,
      "data_current_modified":False,"validation_material_used":False,"post_result_model_tuning_authorized":False,
      "canonical_sha256":CANON_SHA,"r10a_queue_sha256":QUEUE_SHA,"v42_engine_sha256":ENGINE_SHA,
      "pre_run_checks":checks,"candidate_sha256":sha(candidate_path),
      "outputs":{n:{"sha256":sha(out/n),"bytes":(out/n).stat().st_size} for n in outs},
      "next_gate":"R10C_FROZEN_ENGINE_RERUN_ON_R10B_CANDIDATE",
    }
    (out/"V4_2_R10B_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print("R10B COMPLETE")
    print(json.dumps(agg,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
