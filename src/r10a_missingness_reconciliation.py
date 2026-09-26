#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json,math,os
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CANON=ROOT/"data/current/sp500_fundamentals.csv"
R10=ROOT/"data/v4_2/r10/36264099847"
COMP=R10/"V4_2_R10_FULL_COMPARISON.csv"
AGG=R10/"V4_2_R10_AGGREGATES.json"
REC=R10/"V4_2_R10_RECEIPT.json"
MAN=ROOT/"docs/V4_2_ENGINE_MANIFEST.json"
CANON_SHA="d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45"
COMP_SHA="6ad6979068054c173726b849e71f22552c181483ea4075b99cea9db0a6b7bf71"
ENGINE_SHA="cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e"
EXPECTED_BLOCKED=150
EXPECTED_GATES={"SBC MISSING/CONFLICTING":40,"capex MISSING/CONFLICTING":22,
"guarded growth inputs MISSING/CONFLICTING":38,"share_change MISSING/CONFLICTING":50}

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
def rows(p):
    with p.open("r",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def num(v):
    s=str(v or "").strip()
    if s in ("","nan","None","MISSING","NA","NOT_APPLICABLE","CONFLICTING"):return None
    try:x=float(s)
    except:return None
    return x if math.isfinite(x) else None
def txt(v):return bool(str(v or "").strip())
def cagr(cur,old):
    if cur is None or old is None or cur<=0 or old<=0:return None
    return (cur/old)**(1/3)-1
def fcf(o,c):return None if o is None or c is None else o-abs(c)
def ps(v,s):return None if v is None or s is None or s<=0 else v/s
def sch(cur,prior):return None if cur is None or prior in (None,0) else cur/prior-1

def direct(label,value,r):
    if value is not None:return []
    if not txt(r.get("annual_adsh")):return [f"{label}_NO_ANNUAL_FILING"]
    tag=r.get(f"annual_{label.lower()}_tag",""); date=r.get(f"annual_{label.lower()}_date","")
    if txt(tag) or txt(date):return [f"{label}_VALUE_MISSING_WITH_PROVENANCE_METADATA"]
    return [f"{label}_SUPPORTED_XBRL_TAG_NOT_FOUND"]

def audit(c,r):
    variant=(r.get("ios_variant_v42") or "IOS_GENERAL").strip()
    causes=[]; repair=[]; source=[]; noncomp=[]
    capex=num(c.get("annual_capex")); sbc=num(c.get("annual_sbc"))
    if variant=="IOS_GENERAL":
        for label,val in [("CAPEX",capex),("SBC",sbc)]:
            for x in direct(label,val,c):
                causes.append(x)
                (repair if "WITH_PROVENANCE" in x else source).append(x)
    dy=num(c.get("diluted_shares_yoy")); cursh=num(c.get("annual_diluted_shares")); prsh=num(c.get("prior_diluted_shares"))
    if variant in ("IOS_GENERAL","IOS_BANK","IOS_INSURANCE","IOS_REIT") and dy is None:
        if sch(cursh,prsh) is not None:
            x="SHARE_CHANGE_DERIVATION_DEFECT_CANDIDATE";causes.append(x);repair.append(x)
        else:
            if cursh is None:
                x="SHARE_CHANGE_CURRENT_DILUTED_SHARES_MISSING";causes.append(x);source.append(x)
            if prsh is None:
                x="SHARE_CHANGE_PRIOR_DILUTED_SHARES_MISSING";causes.append(x);source.append(x)
            elif prsh==0:
                x="SHARE_CHANGE_PRIOR_DILUTED_SHARES_ZERO";causes.append(x);noncomp.append(x)
    revg=num(c.get("revenue_cagr3")); fpsg=num(c.get("fcf_per_share_cagr3"))
    if variant=="IOS_GENERAL":
        if revg is None:
            cur=num(c.get("annual_revenue")); old=num(c.get("fy_minus_3_revenue"))
            if cagr(cur,old) is not None:
                x="REVENUE_CAGR_DERIVATION_DEFECT_CANDIDATE";causes.append(x);repair.append(x)
            else:
                if cur is None:
                    x="REVENUE_CAGR_CURRENT_REVENUE_MISSING";causes.append(x);source.append(x)
                if old is None:
                    x="REVENUE_CAGR_FY_MINUS_3_REVENUE_MISSING";causes.append(x);source.append(x)
                if cur is not None and old is not None and (cur<=0 or old<=0):
                    x="REVENUE_CAGR_NONPOSITIVE_ENDPOINT";causes.append(x);noncomp.append(x)
        if fpsg is None:
            vals={k:num(c.get(v)) for k,v in {
                "CURRENT_OCF":"annual_operating_cash_flow","CURRENT_CAPEX":"annual_capex",
                "CURRENT_DILUTED_SHARES":"annual_diluted_shares","FY_MINUS_3_OCF":"fy_minus_3_operating_cash_flow",
                "FY_MINUS_3_CAPEX":"fy_minus_3_capex","FY_MINUS_3_DILUTED_SHARES":"fy_minus_3_diluted_shares"}.items()}
            curfps=ps(fcf(vals["CURRENT_OCF"],vals["CURRENT_CAPEX"]),vals["CURRENT_DILUTED_SHARES"])
            oldfps=ps(fcf(vals["FY_MINUS_3_OCF"],vals["FY_MINUS_3_CAPEX"]),vals["FY_MINUS_3_DILUTED_SHARES"])
            if cagr(curfps,oldfps) is not None:
                x="FCF_PER_SHARE_CAGR_DERIVATION_DEFECT_CANDIDATE";causes.append(x);repair.append(x)
            else:
                for k,v in vals.items():
                    if v is None:
                        x=f"FCF_PER_SHARE_CAGR_{k}_MISSING";causes.append(x);source.append(x)
                if curfps is not None and oldfps is not None and (curfps<=0 or oldfps<=0):
                    x="FCF_PER_SHARE_CAGR_NONPOSITIVE_ENDPOINT";causes.append(x);noncomp.append(x)
    if not causes:
        causes=["UNEXPLAINED_R10_BLOCK"];klass="UNEXPLAINED_REQUIRES_TECHNICAL_REVIEW"
    elif repair and not source and not noncomp:klass="DETERMINISTIC_REPAIRABLE_FROM_EXISTING_CANONICAL"
    elif source and not repair and not noncomp:klass="SOURCE_RECOVERY_REQUIRED"
    elif noncomp and not repair and not source:klass="ECONOMICALLY_NONCOMPUTABLE_FROM_EXISTING_SERIES"
    else:klass="MULTI_CAUSE"
    return {"ticker":r["ticker"],"name":r.get("name",""),"module":r.get("module_v42_r10",""),
    "ios_variant_v42":variant,"r10_first_gate":r.get("ios_gate_v42",""),
    "root_cause_count":len(set(causes)),"root_causes":"|".join(sorted(set(causes))),"repair_class":klass,
    "deterministic_repair_candidates":"|".join(sorted(set(repair))),
    "source_recovery_requirements":"|".join(sorted(set(source))),
    "noncomputable_reasons":"|".join(sorted(set(noncomp)))}

def write_csv(p,rs,fields):
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rs)

def main():
    run=os.getenv("GITHUB_RUN_ID","LOCAL");out=ROOT/"data/v4_2/r10a"/run;out.mkdir(parents=True,exist_ok=True)
    for p in [CANON,COMP,AGG,REC,MAN]:
        if not p.exists():raise SystemExit(f"missing {p}")
    rec=json.loads(REC.read_text());agg=json.loads(AGG.read_text());man=json.loads(MAN.read_text())
    checks={"canonical_sha":sha(CANON)==CANON_SHA,"r10_comparison_sha":sha(COMP)==COMP_SHA,
    "r10_frozen":rec.get("frozen") is True,"post_result_tuning_forbidden":rec.get("post_result_tuning_authorized") is False,
    "engine_frozen":man.get("frozen") is True,"engine_sha":man.get("v4_2_engine_sha256")==ENGINE_SHA,
    "blocked_count":agg.get("v41_numeric_to_v42_blocked")==EXPECTED_BLOCKED,"gate_counts":agg.get("blocked_reasons")==EXPECTED_GATES}
    if not all(checks.values()):raise SystemExit("seal fail: "+",".join(k for k,v in checks.items() if not v))
    canon={r["ticker"].strip():r for r in rows(CANON)}
    comp=rows(COMP);blocked=[r for r in comp if num(r.get("ios_v41")) is not None and num(r.get("ios_v42")) is None]
    if len(blocked)!=EXPECTED_BLOCKED:raise SystemExit(f"blocked {len(blocked)} != {EXPECTED_BLOCKED}")
    audits=[audit(canon[r["ticker"]],r) for r in blocked]
    fields=list(audits[0].keys())
    write_csv(out/"V4_2_R10A_MISSINGNESS_AUDIT.csv",audits,fields)
    repairs=[r for r in audits if r["deterministic_repair_candidates"]]
    sources=[r for r in audits if r["source_recovery_requirements"]]
    write_csv(out/"V4_2_R10A_DETERMINISTIC_REPAIR_CANDIDATES.csv",repairs,fields)
    write_csv(out/"V4_2_R10A_SOURCE_RECOVERY_QUEUE.csv",sources,fields)
    rc=Counter(r["repair_class"] for r in audits);roots=Counter();repc=Counter();srcc=Counter();ncc=Counter()
    for r in audits:
        for x in filter(None,r["root_causes"].split("|")):roots[x]+=1
        for x in filter(None,r["deterministic_repair_candidates"].split("|")):repc[x]+=1
        for x in filter(None,r["source_recovery_requirements"].split("|")):srcc[x]+=1
        for x in filter(None,r["noncomputable_reasons"].split("|")):ncc[x]+=1
    tech=sum(bool(r["deterministic_repair_candidates"]) for r in audits)
    srcn=sum(bool(r["source_recovery_requirements"]) for r in audits)
    non=sum(bool(r["noncomputable_reasons"]) for r in audits)
    unexpl=sum("UNEXPLAINED_R10_BLOCK" in r["root_causes"] for r in audits)
    flags=[]
    if tech:flags.append("DATA_DERIVATION_REPAIR_REQUIRED")
    if srcn:flags.append("PRIMARY_SOURCE_RECOVERY_REQUIRED")
    if unexpl:flags.append("UNEXPLAINED_BLOCKS_REQUIRE_TECHNICAL_REVIEW")
    status="RECONCILIATION_REQUIRED" if flags else "NO_DATA_LAYER_ACTION_IDENTIFIED"
    a={"schema":"investment_os_v4_2_r10a_aggregates_v1.0","run_id":run,"system_live":False,
    "engine_modified":False,"ranking_recomputed":False,"external_data_fetched":False,"data_current_modified":False,
    "blocked_rows_audited":len(audits),"repair_class_counts":dict(sorted(rc.items())),
    "root_cause_occurrences":dict(sorted(roots.items())),"deterministic_repair_code_occurrences":dict(sorted(repc.items())),
    "source_recovery_code_occurrences":dict(sorted(srcc.items())),"noncomputable_code_occurrences":dict(sorted(ncc.items())),
    "rows_with_deterministic_repair_candidate":tech,"rows_requiring_primary_source_recovery":srcn,
    "rows_with_economically_noncomputable_series":non,"unexplained_rows":unexpl,
    "review_status":status,"decision_flags":flags}
    (out/"V4_2_R10A_AGGREGATES.json").write_text(json.dumps(a,indent=2)+"\n")
    plan=f"""# V4.2 R10A — Missingness Reconciliation

- Blocked rows audited: **{len(audits)}**
- Deterministic repair candidates: **{tech}**
- Primary-source recovery rows: **{srcn}**
- Economically non-computable rows: **{non}**
- Unexplained rows: **{unexpl}**
- Review status: **{status}**
- Decision flags: **{', '.join(flags) if flags else 'none'}**

R10A changes no engine rule and does not recompute a ranking.

If deterministic repair candidates exist, the next step is a V4.2 data-layer derivation patch with regression tests.
If primary-source recovery is required, the next step is generic primary-filing recovery with provenance.
No missing value may be converted to zero. `data/current` remains immutable.
Any substantive scoring-model change requires a new version/change-control cycle.

**System remains NOT LIVE.**
"""
    (out/"V4_2_R10A_REMEDIATION_PLAN.md").write_text(plan)
    outs=["V4_2_R10A_MISSINGNESS_AUDIT.csv","V4_2_R10A_DETERMINISTIC_REPAIR_CANDIDATES.csv",
    "V4_2_R10A_SOURCE_RECOVERY_QUEUE.csv","V4_2_R10A_AGGREGATES.json","V4_2_R10A_REMEDIATION_PLAN.md"]
    receipt={"schema":"investment_os_v4_2_r10a_receipt_v1.0","stage":"R10A_MISSINGNESS_RECONCILIATION",
    "run_id":run,"frozen":True,"system_live":False,"engine_modified":False,"ranking_recomputed":False,
    "external_data_fetched":False,"data_current_modified":False,"validation_material_used":False,
    "post_result_model_tuning_authorized":False,"canonical_sha256":CANON_SHA,"r10_comparison_sha256":COMP_SHA,
    "v42_engine_sha256":ENGINE_SHA,"pre_run_checks":checks,"review_status":status,"decision_flags":flags,
    "outputs":{n:{"sha256":sha(out/n),"bytes":(out/n).stat().st_size} for n in outs},
    "next_gate":"R10B_DATA_LAYER_REMEDIATION_OR_SOURCE_RECOVERY"}
    (out/"V4_2_R10A_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print("R10A COMPLETE",json.dumps(a,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
