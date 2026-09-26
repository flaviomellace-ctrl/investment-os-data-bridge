#!/usr/bin/env python3
"""
Investment OS V4.2 — R10D real-overlay evidence scan.

Uses the frozen R10C result to build the frozen 7+3 deep-dive queue, then retrieves
primary SEC evidence for ONLY those 10 queue companies.

Outputs:
- deterministic Lane V / Lane I / 7+3 queue;
- conservative BR-09 evidence scan + classifier result;
- R6/R7 cash-quality, commitments, and leverage-stress diagnostics.

No BQS/IOS formula changes. No BUY/ADD. No fresh market data. No validation target.
"""

from __future__ import annotations
import csv,gzip,hashlib,html,json,math,os,re,sys,time,urllib.request,zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Any,Dict,List,Optional,Sequence
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
R10C=ROOT/"data/v4_2/r10c/36268612607"
R10C_COMP=R10C/"V4_2_R10C_FULL_COMPARISON.csv"
R10C_REC=R10C/"V4_2_R10C_RECEIPT.json"
R10B=ROOT/"data/v4_2/r10b/36268043494"
CAND=R10B/"V4_2_R10B_CANDIDATE_FUNDAMENTALS.csv"
V41=ROOT/"data/blind_v4_1/36045268572/quantitative/V4_1_RANKING_FULL.csv"
LANE=ROOT/"src/inflection_lane_v42.py"
MARKET=ROOT/"src/marketplace_classifier_v42.py"
CASH=ROOT/"src/cash_quality_commitments_v42.py"

R10C_COMP_SHA="7069635e5bf147ba0f8078ca4df8288fbb20f3c573d668de285caa89b83fc2c0"
CAND_SHA="979914c918cdd5771409bca679ce8e84f3224bb602ed36c0e1dcfb71fbd920c6"
V41_SHA="fe6aa604ca9529e2ffa53927581c509e213dc0d034072e6508a6c3ae0d1542b0"
SEC_MIN_SECONDS=0.35

# BR-09 Phase-0 accounting archetype thresholds frozen BEFORE this real-text scan.
# "Capital-light intermediation" requires BOTH conditions.
MAX_COGS_TO_REVENUE=0.35
MAX_CAPEX_TO_REVENUE=0.05

ANNUAL_FORMS={"10-K","20-F","40-F"}
COGS_CONCEPTS=[
 ("us-gaap","CostOfRevenue","USD"),
 ("us-gaap","CostOfGoodsAndServicesSold","USD"),
 ("us-gaap","CostOfGoodsSold","USD"),
]
DA_CONCEPTS=[
 ("us-gaap","DepreciationDepletionAndAmortization","USD"),
 ("us-gaap","DepreciationDepletionAndAmortizationPropertyPlantAndEquipment","USD"),
 ("us-gaap","DepreciationAndAmortization","USD"),
 ("us-gaap","Depreciation","USD"),
]

AGENCY_NET_TERMS=[
 "principal versus agent","principal or agent","agent in the transaction",
 "reported on a net basis","recognize revenue on a net basis","gross versus net",
]
INTERMEDIATION_TERMS=[
 "marketplace","platform connects","platform connecting","connect buyers and sellers",
 "connect consumers","connect customers","brings together buyers and sellers",
 "two-sided platform","two sided platform","two-sided marketplace","two sided marketplace",
]
TWO_SIDED_TERMS=[
 "two-sided marketplace","two sided marketplace","two-sided platform","two sided platform",
 "connect buyers and sellers","brings together buyers and sellers","connect consumers with",
 "connect customers with","connect guests with","connect riders with","connect merchants with",
]
VOLUME_TERMS=[
 "gross bookings","gross merchandise value","gross transaction value","gross order value",
 "gross payment volume","gross volume","transaction volume","marketplace volume","gmv",
]
CASH_WC_TERMS=["working capital release","working capital benefited","benefit from working capital","unusual working capital"]
CASH_TAX_TERMS=["tax timing","timing of tax payments","tax payment timing"]
CASH_RESERVE_TERMS=["reserve release","increase in float","reserve development"]
CASH_REVAL_TERMS=["non-cash remeasurement","noncash remeasurement","fair value remeasurement"]
PURCHASE_TERMS=["purchase obligations","purchase commitments","minimum purchase commitments"]
GUARANTEE_TERMS=["guarantees of obligations","guaranteed obligations","financial guarantees"]
OFFBAL_TERMS=["off-balance sheet","off balance sheet"]

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
def load(name,p):
    sp=importlib.util.spec_from_file_location(name,p)
    if sp is None or sp.loader is None:
        raise RuntimeError(f"cannot import {p}")
    m=importlib.util.module_from_spec(sp)
    sys.modules[name]=m
    sp.loader.exec_module(m)
    return m
def cik10(v):
    try:return str(int(float(str(v).strip()))).zfill(10)
    except:return ""
def norm_period(v):
    try:
        x=float(str(v).strip())
        if x.is_integer() and len(str(int(x)))==8:
            s=str(int(x));return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except:pass
    s="".join(ch for ch in str(v or "") if ch.isdigit())
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s)==8 else ""
def decode(raw,enc):
    e=(enc or "").lower().strip()
    if e=="gzip":return gzip.decompress(raw)
    if e=="deflate":
        try:return zlib.decompress(raw)
        except:return zlib.decompress(raw,-zlib.MAX_WBITS)
    return raw
def fetch_json(url,email,last):
    elapsed=time.monotonic()-last[0]
    if elapsed<SEC_MIN_SECONDS:time.sleep(SEC_MIN_SECONDS-elapsed)
    req=urllib.request.Request(url,headers={"User-Agent":f"InvestmentOSDataBridge/1.0 {email}","Accept-Encoding":"gzip, deflate","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=45) as r:
        raw=r.read();enc=r.headers.get("Content-Encoding","")
    last[0]=time.monotonic()
    return json.loads(decode(raw,enc).decode("utf-8-sig"))
def fetch_bytes(url,email,last):
    elapsed=time.monotonic()-last[0]
    if elapsed<SEC_MIN_SECONDS:time.sleep(SEC_MIN_SECONDS-elapsed)
    req=urllib.request.Request(url,headers={"User-Agent":f"InvestmentOSDataBridge/1.0 {email}","Accept-Encoding":"gzip, deflate"})
    with urllib.request.urlopen(req,timeout=45) as r:
        raw=r.read();enc=r.headers.get("Content-Encoding","")
    last[0]=time.monotonic();return decode(raw,enc)

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
def html_to_text(raw):
    p=TextExtractor();p.feed(raw.decode("utf-8","ignore"))
    return re.sub(r"\s+"," ",html.unescape(" ".join(p.parts))).strip().lower()

def find_hits(text,terms):
    return sorted({t for t in terms if t in text})
def short_context(text,term,words=18):
    i=text.find(term)
    if i<0:return ""
    frag=text[max(0,i-140):i+len(term)+140]
    toks=frag.split()
    return " ".join(toks[:words])

def select_companyfact(cf,concepts,target_end):
    if not target_end:return None
    for tax,concept,unit in concepts:
        vals=cf.get("facts",{}).get(tax,{}).get(concept,{}).get("units",{}).get(unit,[])
        cand=[]
        for x in vals:
            if str(x.get("form","")).upper() not in ANNUAL_FORMS or x.get("end")!=target_end or "start" not in x:continue
            try:v=float(x["val"])
            except:continue
            if not math.isfinite(v):continue
            cand.append((str(x.get("filed","")),str(x.get("accn","")),v,x,concept))
        if cand:
            cand.sort(reverse=True);_,_,v,x,c=cand[0]
            return {"value":v,"concept":c,"filed":x.get("filed",""),"accn":x.get("accn","")}
    return None

def latest_annual_filing(sub,cik):
    recent=sub.get("filings",{}).get("recent",{})
    forms=recent.get("form",[]);accs=recent.get("accessionNumber",[]);docs=recent.get("primaryDocument",[])
    dates=recent.get("filingDate",[]);reports=recent.get("reportDate",[])
    for i,f in enumerate(forms):
        if str(f).upper() in ANNUAL_FORMS:
            acc=accs[i];doc=docs[i]
            url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}"
            return {"form":f,"accession":acc,"primary_document":doc,"filing_date":dates[i],"report_date":reports[i],"url":url}
    return None

def main():
    run=os.getenv("GITHUB_RUN_ID","LOCAL");out=ROOT/"data/v4_2/r10d"/run;out.mkdir(parents=True,exist_ok=True)
    email=os.getenv("SEC_CONTACT_EMAIL","").strip()
    if "@" not in email:raise SystemExit("SEC_CONTACT_EMAIL required")
    checks={"r10c_sha":sha(R10C_COMP)==R10C_COMP_SHA,"candidate_sha":sha(CAND)==CAND_SHA,"v41_sha":sha(V41)==V41_SHA}
    if not all(checks.values()):raise SystemExit("seal fail")
    lane=load("lane",LANE);market=load("market",MARKET);cash=load("cash",CASH)
    comp=rows(R10C_COMP);cand=rows(CAND);v41=rows(V41)
    cb={r["ticker"]:r for r in cand};gb={r["ticker"]:r for r in v41}

    lane_v=[{"entity_key":r["ticker"],"ticker":r["ticker"],"name":r["name"],"ios":num(r["ios_r10c"]),"bqs":num(r["bqs_r10c"]),"ios_rank":num(r["ios_rank_r10c"])}
            for r in comp if num(r["ios_r10c"]) is not None]
    lane_v.sort(key=lambda r:int(r["ios_rank"]))
    lane_i_input=[]
    for r in comp:
        c=cb[r["ticker"]];ocf=num(c.get("annual_operating_cash_flow"));capex=num(c.get("annual_capex"));sbc=num(c.get("annual_sbc"));ni=num(c.get("annual_net_income"))
        oe=None if None in (ocf,capex,sbc) else ocf-capex-sbc
        conv=None if ocf is None or ni in (None,0) else ocf/ni
        flags=[x for x in (gb.get(r["ticker"],{}).get("growth_flags","") or "").split("|") if x]
        lane_i_input.append({"entity_key":r["ticker"],"ticker":r["ticker"],"name":r["name"],"bqs":num(r["bqs_r10c"]),
          "owner_earnings":oe,"revenue_cagr3":num(c.get("revenue_cagr3")),"fcf_cagr3":num(c.get("fcf_cagr3")),
          "fcf_per_share_cagr3":num(c.get("fcf_per_share_cagr3")),"cash_conversion":conv,
          "share_change":num(c.get("diluted_shares_yoy")),"growth_flags":flags,"quality_flags":[],"cyclical_rebound_flag":False})
    lane_i=lane.rank_lane_i(lane_i_input)
    queue=lane.merge_deep_dive_queue(lane_v,lane_i)
    qrows=[]
    for i,r in enumerate(queue,1):
        qrows.append({"queue_rank":i,"ticker":r["ticker"],"name":r["name"],"selection_lane":r["selection_lane"],
                      "ios":r.get("ios",""),"inflection_score":r.get("score",""),"bqs":r.get("bqs","")})
    write_csv(out/"V4_2_R10D_DEEP_DIVE_QUEUE.csv",qrows,list(qrows[0].keys()))

    last=[0.0];overlay=[];fetch_fail=[]
    for q in qrows:
        t=q["ticker"];c=cb[t];cik=cik10(c.get("cik"));period=norm_period(c.get("annual_period"))
        try:
            cf=fetch_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",email,last)
            sub=fetch_json(f"https://data.sec.gov/submissions/CIK{cik}.json",email,last)
            filing=latest_annual_filing(sub,cik)
            if not filing:raise RuntimeError("annual filing not found")
            raw=fetch_bytes(filing["url"],email,last);text=html_to_text(raw);filing_sha=hashlib.sha256(raw).hexdigest()
        except Exception as e:
            fetch_fail.append({"ticker":t,"error":type(e).__name__});continue

        revenue=num(c.get("annual_revenue"));capex=num(c.get("annual_capex"))
        cogs_fact=select_companyfact(cf,COGS_CONCEPTS,period);cogs=cogs_fact["value"] if cogs_fact else None
        cogs_ratio=None if cogs is None or revenue in (None,0) else cogs/revenue
        capex_ratio=None if capex is None or revenue in (None,0) else abs(capex)/revenue
        capital_light=(cogs_ratio is not None and capex_ratio is not None and cogs_ratio<=MAX_COGS_TO_REVENUE and capex_ratio<=MAX_CAPEX_TO_REVENUE)
        agency_hits=find_hits(text,AGENCY_NET_TERMS);inter_hits=find_hits(text,INTERMEDIATION_TERMS)
        two_hits=find_hits(text,TWO_SIDED_TERMS);vol_hits=find_hits(text,VOLUME_TERMS)
        agency=True if agency_hits else False
        inter=True if inter_hits else False
        tri=market.triage_marketplace(agency_or_net_presentation=agency,capital_light_intermediation=capital_light,intermediation_language=inter)
        two=True if two_hits else False
        revenue_linked=("take rate" in text) or any((v in text and "revenue" in text[max(0,text.find(v)-400):text.find(v)+400]) for v in VOLUME_TERMS)
        reports_volume=bool(vol_hits)
        evidence=market.Evidence(source_type="PRIMARY",source_url_or_accession=filing["accession"],filing_date=filing["filing_date"],
          classification_as_of=filing["report_date"] or filing["filing_date"],
          evidence_excerpt_or_hash=hashlib.sha256(("|".join(agency_hits+inter_hits+two_hits+vol_hits)+"|"+filing_sha).encode()).hexdigest())
        cls=market.classify_marketplace(original_module=next(r["module"] for r in comp if r["ticker"]==t),
          candidate_marketplace=tri["candidate_marketplace"],two_sided_intermediation=two,
          revenue_linked_to_underlying_volume=revenue_linked,company_reports_underlying_volume=reports_volume,evidence=evidence)

        ocf=num(c.get("annual_operating_cash_flow"));sbc=num(c.get("annual_sbc"))
        oe=cash.reported_owner_earnings(ocf,capex,sbc)
        norm=cash.normalize_owner_earnings(reported_oe=oe.get("reported_owner_earnings"),
          positive_temporary_cash_benefits=[],negative_temporary_cash_drags=[],normalization_complete=False)
        cashdiag=cash.cash_quality_diagnostic(reported_oe=oe.get("reported_owner_earnings"),normalized_result=norm,
          working_capital_anomaly=bool(find_hits(text,CASH_WC_TERMS)),
          reserve_or_float_dependency=bool(find_hits(text,CASH_RESERVE_TERMS)),
          tax_timing_anomaly=bool(find_hits(text,CASH_TAX_TERMS)),
          noncash_revaluation_flag=bool(find_hits(text,CASH_REVAL_TERMS)))

        commits=[]
        lease=num(c.get("operating_lease_liabilities"))
        if lease is not None:
            commits.append(cash.Commitment("OPERATING_LEASE_LIABILITY",lease,cash.PRESENT,False,False,filing["accession"],filing["report_date"],"reported operating lease liability"))
        for cat,terms in [("PURCHASE_OBLIGATIONS",PURCHASE_TERMS),("GUARANTEES",GUARANTEE_TERMS),("OFF_BALANCE_ARRANGEMENTS",OFFBAL_TERMS)]:
            if find_hits(text,terms):
                commits.append(cash.Commitment(cat,None,cash.MISSING,True,False,filing["accession"],filing["report_date"],"primary filing lexical trigger; amount requires reconciliation"))
        comdiag=cash.commitments_diagnostic(commits,owner_earnings=oe.get("reported_owner_earnings"))

        da_fact=select_companyfact(cf,DA_CONCEPTS,period);da=da_fact["value"] if da_fact else None
        opinc=num(c.get("annual_operating_income"));ebitda=None if opinc is None or da is None else opinc+da
        lev=cash.leverage_stress_view(gross_debt=num(c.get("total_debt")),cash=num(c.get("cash_and_equivalents")),
          ebitda=ebitda,sbc=sbc,module=next(r["module"] for r in comp if r["ticker"]==t))

        overlay.append({
          "queue_rank":q["queue_rank"],"ticker":t,"selection_lane":q["selection_lane"],
          "filing_accession":filing["accession"],"filing_date":filing["filing_date"],"report_date":filing["report_date"],"filing_sha256":filing_sha,
          "agency_net_signal":agency,"capital_light_signal":capital_light,"intermediation_signal":inter,
          "br09_candidate":tri["candidate_marketplace"],"two_sided_evidence":two,"revenue_linked_volume_evidence":revenue_linked,
          "company_reports_volume":reports_volume,"br09_final_module":cls["final_module"],"br09_status":cls["classification_status"],"br09_reason":cls["reason_code"],
          "cogs_to_revenue":cogs_ratio if cogs_ratio is not None else "","capex_to_revenue":capex_ratio if capex_ratio is not None else "",
          "cash_quality_gate":cashdiag["decision_gate_action"],"cash_quality_flags":"|".join(cashdiag["cash_quality_flags"]),
          "commitments_gate":comdiag["decision_gate_action"],"unresolved_material_commitments":"|".join(comdiag["unresolved_material_categories"]),
          "quantified_uncovered_commitments":comdiag["quantified_uncovered_commitments"],
          "leverage_status":lev.get("status",""),"leverage_risk_band":lev.get("risk_band",""),"debt_to_ebitda_after_sbc":lev.get("gross_debt_to_ebitda_after_sbc",""),
          "evidence_match_hash":evidence.evidence_excerpt_or_hash,
        })

    if fetch_fail:raise SystemExit("SEC fetch failures: "+json.dumps(fetch_fail))
    fields=list(overlay[0].keys());write_csv(out/"V4_2_R10D_REAL_OVERLAYS.csv",overlay,fields)
    provisional=sum(r["br09_status"]=="PROVISIONAL" for r in overlay)
    gates=sum(r["cash_quality_gate"]!="NO_ADDITIONAL_CASH_QUALITY_BLOCK" or r["commitments_gate"]=="INVESTIGARE" for r in overlay)
    agg={"schema":"investment_os_v4_2_r10d_aggregates_v1.0","run_id":run,"system_live":False,"queue_count":len(qrows),
         "overlay_count":len(overlay),"br09_provisional_count":provisional,"candidates_with_r6r7_reconcile_or_investigate":gates,
         "marketplace_verified_count":sum(r["br09_final_module"]=="MARKETPLACE_NETWORK" and r["br09_status"]=="VERIFIED" for r in overlay),
         "engine_modified":False,"ranking_recomputed":False,"fresh_market_data_used":False}
    (out/"V4_2_R10D_AGGREGATES.json").write_text(json.dumps(agg,indent=2)+"\n")
    report=f"""# V4.2 R10D — Real overlay evidence scan

- Deep-dive queue: **{len(qrows)}**
- Real SEC overlays completed: **{len(overlay)}**
- BR-09 provisional classifications: **{provisional}**
- Verified MARKETPLACE_NETWORK classifications: **{agg['marketplace_verified_count']}**
- Candidates requiring R6/R7 reconcile/investigate: **{gates}**

This stage does not rerank securities and does not emit investment actions.
Any BR-09 provisional case or R6/R7 investigate flag must be resolved before independent blind validation.

**System remains NOT LIVE.**
"""
    (out/"V4_2_R10D_REPORT.md").write_text(report)
    outs=["V4_2_R10D_DEEP_DIVE_QUEUE.csv","V4_2_R10D_REAL_OVERLAYS.csv","V4_2_R10D_AGGREGATES.json","V4_2_R10D_REPORT.md"]
    rec={"schema":"investment_os_v4_2_r10d_receipt_v1.0","stage":"R10D_REAL_OVERLAYS","run_id":run,"frozen":True,
         "system_live":False,"engine_modified":False,"ranking_recomputed":False,"validation_material_used":False,
         "pre_run_checks":checks,"outputs":{n:{"sha256":sha(out/n),"bytes":(out/n).stat().st_size} for n in outs},
         "next_gate":"RESOLVE_PROVISIONAL_BR09_AND_R6_R7_FLAGS_THEN_R11_HIDDEN_CONTROLS"}
    (out/"V4_2_R10D_RECEIPT.json").write_text(json.dumps(rec,indent=2)+"\n")
    print("R10D COMPLETE");print(json.dumps(agg,indent=2));return 0

if __name__=="__main__":raise SystemExit(main())
