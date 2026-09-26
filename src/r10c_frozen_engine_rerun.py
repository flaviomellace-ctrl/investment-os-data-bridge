#!/usr/bin/env python3
"""
Investment OS V4.2 — R10C frozen-engine rerun on frozen R10B data candidate.

Purpose:
- rerun the already-frozen V4.2 BQS+IOS engine on the R10B SEC-recovered candidate;
- keep module routing and market snapshot frozen to R10;
- measure how much data recovery restores calculability and changes rankings.

Forbidden:
- no fresh market data;
- no model/threshold/weight changes;
- no validation target;
- no BR-09 documentary rerouting yet;
- no BUY/ADD;
- no write to data/current.
"""

from __future__ import annotations
import csv,hashlib,importlib.util,json,math,os,statistics
from collections import Counter
from pathlib import Path
from typing import Any,Dict,List,Optional,Sequence

ROOT=Path(__file__).resolve().parents[1]
R10=ROOT/"data/v4_2/r10/36264099847"
R10_COMP=R10/"V4_2_R10_FULL_COMPARISON.csv"
R10_AGG=R10/"V4_2_R10_AGGREGATES.json"
R10B=ROOT/"data/v4_2/r10b/36268043494"
CAND=R10B/"V4_2_R10B_CANDIDATE_FUNDAMENTALS.csv"
R10B_REC=R10B/"V4_2_R10B_RECEIPT.json"
PROV=R10B/"V4_2_R10B_RECOVERY_PROVENANCE.csv"
ENGINE=ROOT/"src/investment_os/v4_2/v4_scoring.py"
MAN=ROOT/"docs/V4_2_ENGINE_MANIFEST.json"

R10_COMP_SHA="6ad6979068054c173726b849e71f22552c181483ea4075b99cea9db0a6b7bf71"
CAND_SHA="979914c918cdd5771409bca679ce8e84f3224bb602ed36c0e1dcfb71fbd920c6"
PROV_SHA="1eb6937ff390a9dad591f87d816c01e56333e99a8e4c93ab3e66707862bad224"
ENGINE_SHA="cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e"
CANON_SHA="d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45"
EXPECTED_ROWS=504

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()
def rows(p):
    with p.open("r",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rs,fields):
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader()
        for r in rs:w.writerow({k:r.get(k,"") for k in fields})
def num(v):
    s=str(v or "").strip()
    if s in ("","nan","None","MISSING","NA","NOT_APPLICABLE","CONFLICTING"):return None
    try:x=float(s)
    except:return None
    return x if math.isfinite(x) else None
def sentinel(v,e):
    s=str(v or "").strip()
    if s=="NOT_APPLICABLE":return e.NA
    if s=="CONFLICTING":return e.CONFLICTING
    return num(v)
def load(name,path):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def ratio(a,b):
    return None if a is None or b in (None,0) else a/b
def median(xs):
    return round(statistics.median(xs),4) if xs else None

def adapt(cr,br,e):
    rev=num(cr.get("annual_revenue")); ni=num(cr.get("annual_net_income"))
    ocf=num(cr.get("annual_operating_cash_flow")); capex=num(cr.get("annual_capex"))
    eq=num(cr.get("annual_equity")); assets=num(cr.get("annual_assets"))
    ba=str(cr.get("buyback_accretion") or "").strip()
    buy=e.NA if ba=="NOT_APPLICABLE" else num(ba)
    return {
      "module":br.get("module_v42_r10") or "GENERAL",
      "data_coverage_pct":num(br.get("data_coverage_pct")) or 0.0,
      "op_margin":num(cr.get("operating_margin")),
      "fcf_margin":num(cr.get("fcf_margin")),
      "net_margin":num(cr.get("net_margin")),
      "roe":num(cr.get("roe_simple")),
      "roic":sentinel(cr.get("roic"),e),
      "cash_conversion":ratio(ocf,ni),
      "accrual_quality":ratio(ocf,ni),
      "equity_to_assets":ratio(eq,assets),
      "net_debt_to_ocf":sentinel(cr.get("net_debt_to_ocf"),e),
      "reinvestment_rate":ratio(capex,rev),
      "share_change":num(cr.get("diluted_shares_yoy")),
      "ni_yoy":num(cr.get("net_income_yoy")),
      "book_value":eq,
      "ocf":ocf,"capex":capex,
      "revenue_cagr3":num(cr.get("revenue_cagr3")),
      "opinc_cagr3":num(cr.get("opinc_cagr3")),
      "fcf_cagr3":num(cr.get("fcf_cagr3")),
      "fcf_per_share_cagr3":num(cr.get("fcf_per_share_cagr3")),
      "margin_stability":num(cr.get("operating_margin_std_4y")),
      "sbc":num(cr.get("annual_sbc")),
      "sbc_to_revenue":num(cr.get("sbc_to_revenue")),
      "market_cap":num(br.get("market_cap_frozen")),
      "price":num(br.get("market_price_frozen")),
      "buyback_accretion":buy,
      "payout_ratio":num(cr.get("payout_ratio")),
      "interest_coverage":sentinel(cr.get("interest_coverage"),e),
      "retention":None,"unit_cost_decline":None,"two_sided_growth":None,"frequency_growth":None,
      "combined_ratio":num(cr.get("combined_ratio")),"ffo_margin":num(cr.get("ffo_margin")),
      "occupancy":num(cr.get("occupancy")),"ebitda_on_volume":num(cr.get("ebitda_on_volume")),
      "fcf_on_volume":num(cr.get("fcf_on_volume")),"take_rate":num(cr.get("take_rate")),
      "affo":num(cr.get("affo")),
    }

def main():
    run=os.getenv("GITHUB_RUN_ID","LOCAL");out=ROOT/"data/v4_2/r10c"/run;out.mkdir(parents=True,exist_ok=True)
    for p in [R10_COMP,R10_AGG,CAND,R10B_REC,PROV,ENGINE,MAN]:
        if not p.exists():raise SystemExit(f"missing {p}")
    r10b=json.loads(R10B_REC.read_text());man=json.loads(MAN.read_text());r10agg=json.loads(R10_AGG.read_text())
    checks={
      "r10_comparison_sha":sha(R10_COMP)==R10_COMP_SHA,
      "candidate_sha":sha(CAND)==CAND_SHA,
      "provenance_sha":sha(PROV)==PROV_SHA,
      "r10b_frozen":r10b.get("frozen") is True,
      "r10b_candidate_sha":r10b.get("candidate_sha256")==CAND_SHA,
      "engine_sha":sha(ENGINE)==ENGINE_SHA,
      "manifest_engine_sha":man.get("v4_2_engine_sha256")==ENGINE_SHA,
      "manifest_frozen":man.get("frozen") is True,
      "canonical_immutable":r10b.get("canonical_sha256")==CANON_SHA,
    }
    if not all(checks.values()):raise SystemExit("R10C seal fail: "+",".join(k for k,v in checks.items() if not v))
    e=load("v42_r10c",ENGINE)
    comp=rows(R10_COMP);cand=rows(CAND)
    if len(comp)!=EXPECTED_ROWS or len(cand)!=EXPECTED_ROWS:raise SystemExit("unexpected row count")
    cb={r["ticker"].strip():r for r in cand};bb={r["ticker"].strip():r for r in comp}
    if set(cb)!=set(bb):raise SystemExit("candidate/baseline universe mismatch")

    results=[]
    for t in sorted(bb):
        br=bb[t]; cr=cb[t]; c=adapt(cr,br,e)
        b,bqcov,detail,flags=e.bqs(c)
        metric_cov=detail.get("_metric_coverage_pct",0.0) if isinstance(detail,dict) else 0.0
        status=cr.get("data_status","")
        conf=e.bqs_confidence(bqcov,c["data_coverage_pct"],status,metric_cov,detail.get("_provisional_components",[]) if isinstance(detail,dict) else [])
        ios,idet=e.ios(c,b,bqcov)
        results.append({
          "ticker":t,"name":br.get("name",""),"module":c["module"],
          "bqs_r10":br.get("bqs_v42",""),"bqs_r10c":b if b is not None else "",
          "bqs_coverage_r10c":bqcov,"metric_coverage_r10c":metric_cov,"bqs_confidence_r10c":conf,
          "ios_r10":br.get("ios_v42",""),"ios_rank_r10":br.get("ios_rank_v42",""),
          "ios_r10c":ios if ios is not None else "","ios_rank_r10c":"",
          "ios_variant_r10c":idet.get("variant",e.ios_variant(c["module"])),
          "ios_gate_r10c":idet.get("gate","") if ios is None else "",
          "growth_used_r10c":idet.get("growth_used",""),"expected_return_r10c":idet.get("exp_ret",""),
          "margin_of_safety_r10c":idet.get("mos",""),
        })
    numeric=[r for r in results if num(r["ios_r10c"]) is not None]
    numeric.sort(key=lambda r:(-float(r["ios_r10c"]),-float(r["bqs_r10c"]),r["ticker"]))
    for i,r in enumerate(numeric,1):r["ios_rank_r10c"]=i

    r10_num={r["ticker"] for r in results if num(r["ios_r10"]) is not None}
    r10c_num={r["ticker"] for r in results if num(r["ios_r10c"]) is not None}
    restored=sorted(r10c_num-r10_num);lost=sorted(r10_num-r10c_num)
    common=sorted(r10_num&r10c_num)
    ios_deltas=[num(next(r for r in results if r["ticker"]==t)["ios_r10c"])-num(next(r for r in results if r["ticker"]==t)["ios_r10"]) for t in common]
    bqs_deltas=[]
    for r in results:
        a=num(r["bqs_r10"]);b=num(r["bqs_r10c"])
        if a is not None and b is not None:bqs_deltas.append(b-a)

    gate_counts=Counter(r["ios_gate_r10c"] or "CALCULABLE" for r in results)
    top20_r10=[r["ticker"] for r in sorted([x for x in results if num(x["ios_r10"]) is not None],key=lambda x:int(float(x["ios_rank_r10"])))[:20]]
    top20_r10c=[r["ticker"] for r in numeric[:20]]
    overlap=len(set(top20_r10)&set(top20_r10c))

    agg={
      "schema":"investment_os_v4_2_r10c_aggregates_v1.0","run_id":run,"system_live":False,
      "engine_modified":False,"fresh_market_data_used":False,"validation_material_used":False,
      "universe":len(results),"r10_ios_numeric":len(r10_num),"r10c_ios_numeric":len(r10c_num),
      "restored_ios_numeric":len(restored),"lost_ios_numeric":len(lost),
      "net_ios_numeric_change":len(r10c_num)-len(r10_num),
      "v41_ios_numeric_reference":int(r10agg.get("v41_ios_numeric",0)),
      "remaining_gap_to_v41_numeric":int(r10agg.get("v41_ios_numeric",0))-len(r10c_num),
      "r10c_pool_loss_vs_v41":round((int(r10agg.get("v41_ios_numeric",0))-len(r10c_num))/int(r10agg.get("v41_ios_numeric",1)),6),
      "common_numeric":len(common),"median_ios_delta_common":median(ios_deltas),
      "median_bqs_delta_all_common":median(bqs_deltas),
      "top20_overlap_r10_vs_r10c":overlap,
      "r10c_gate_counts":dict(sorted(gate_counts.items())),
      "restored_tickers":restored,"lost_tickers":lost,
    }
    write_csv(out/"V4_2_R10C_FULL_COMPARISON.csv",results,list(results[0].keys()))
    (out/"V4_2_R10C_AGGREGATES.json").write_text(json.dumps(agg,indent=2)+"\n")
    report=f"""# V4.2 R10C — Frozen engine rerun on R10B candidate

- Universe: **{len(results)}**
- R10 IOS numeric: **{len(r10_num)}**
- R10C IOS numeric: **{len(r10c_num)}**
- IOS newly restored: **{len(restored)}**
- IOS lost after BQS/data recomputation: **{len(lost)}**
- Net numeric change: **{len(r10c_num)-len(r10_num):+d}**
- V4.1 numeric reference: **{r10agg.get('v41_ios_numeric')}**
- Remaining numeric gap vs V4.1: **{agg['remaining_gap_to_v41_numeric']}**
- Pool loss vs V4.1: **{100*agg['r10c_pool_loss_vs_v41']:.2f}%**
- Median IOS delta on common calculable rows: **{agg['median_ios_delta_common']}**
- Median BQS delta on comparable rows: **{agg['median_bqs_delta_all_common']}**
- Top-20 overlap R10 vs R10C: **{overlap}/20**

R10C used the same frozen V4.2 engine, same R10 module routing and same frozen market inputs.
No scoring parameter, threshold or ranking rule was changed.

R10C is still not the final blind validation. BR-09 documentary routing, cash-quality and
commitments overlays remain pending.

**System remains NOT LIVE.**
"""
    (out/"V4_2_R10C_REPORT.md").write_text(report)
    outs=["V4_2_R10C_FULL_COMPARISON.csv","V4_2_R10C_AGGREGATES.json","V4_2_R10C_REPORT.md"]
    receipt={
      "schema":"investment_os_v4_2_r10c_receipt_v1.0","stage":"R10C_FROZEN_ENGINE_RERUN_ON_R10B_CANDIDATE",
      "run_id":run,"frozen":True,"system_live":False,"engine_modified":False,
      "fresh_market_data_used":False,"validation_material_used":False,"post_result_tuning_authorized":False,
      "r10b_candidate_sha256":CAND_SHA,"r10b_provenance_sha256":PROV_SHA,"v42_engine_sha256":ENGINE_SHA,
      "pre_run_checks":checks,"outputs":{n:{"sha256":sha(out/n),"bytes":(out/n).stat().st_size} for n in outs},
      "next_gate":"BR09_AND_R6_R7_REAL_OVERLAYS_BEFORE_INDEPENDENT_BLIND_VALIDATION",
    }
    (out/"V4_2_R10C_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print("R10C COMPLETE");print(json.dumps(agg,indent=2));return 0

if __name__=="__main__":raise SystemExit(main())
