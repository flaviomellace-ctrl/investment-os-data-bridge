from __future__ import annotations
import importlib.util, pathlib, math

P=pathlib.Path(__file__).resolve().parents[1]/"src"/"r10b_primary_source_recovery.py"
s=importlib.util.spec_from_file_location("r10b",P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
PASS=FAIL=0
def check(n,c):
    global PASS,FAIL
    if c:PASS+=1;print("[PASS]",n)
    else:FAIL+=1;print("[FAIL]",n)

def cf(concept,unit,items):
    return {"facts":{"us-gaap":{concept:{"units":{unit:items}}}}}

items=[
 {"start":"2025-01-01","end":"2025-12-31","val":100,"form":"10-K","filed":"2026-02-01","accn":"1"},
 {"start":"2025-10-01","end":"2025-12-31","val":30,"form":"10-Q","filed":"2026-01-20","accn":"2"},
]
x=m.choose_fact(cf("Revenues","USD",items),"revenue","2025-12-31")
check("exact annual fact selected",x and x["value"]==100)
check("quarter fact rejected",x and x["form"]=="10-K")
check("wrong period missing",m.choose_fact(cf("Revenues","USD",items),"revenue","2024-12-31") is None)

items2=[
 {"start":"2025-01-01","end":"2025-12-31","val":0,"form":"10-K","filed":"2026-02-01","accn":"1"}
]
x=m.choose_fact(cf("ShareBasedCompensation","USD",items2),"sbc","2025-12-31")
check("reported zero preserved",x and x["value"]==0)

items3=[
 {"start":"2025-01-01","end":"2025-12-31","val":10,"form":"10-K","filed":"2026-02-01","accn":"1"},
 {"start":"2025-01-01","end":"2025-12-31","val":12,"form":"10-K","filed":"2026-03-01","accn":"2"},
]
x=m.choose_fact(cf("PaymentsToAcquirePropertyPlantAndEquipment","USD",items3),"capex","2025-12-31")
check("latest filed admissible fact selected",x and x["value"]==12 and x["accn"]=="2")

# no fuzzy/custom tag matching
bad={"facts":{"us-gaap":{"MyCompanyCapex":{"units":{"USD":items3}}}}}
check("custom/fuzzy tag rejected",m.choose_fact(bad,"capex","2025-12-31") is None)

r={"annual_revenue":133.1,"fy_minus_3_revenue":100.0,
   "annual_diluted_shares":90.0,"prior_diluted_shares":100.0,
   "annual_operating_cash_flow":40.0,"annual_capex":10.0,
   "fy_minus_3_operating_cash_flow":25.0,"fy_minus_3_capex":5.0,
   "fy_minus_3_diluted_shares":100.0,"annual_sbc":5.0}
changed=m.derive_candidate(r)
check("share change derived",-0.1000001<r["diluted_shares_yoy"]<-0.0999999)
check("revenue CAGR derived",abs(r["revenue_cagr3"]-0.1)<0.001)
check("FCF/share CAGR derived",r["fcf_per_share_cagr3"] is not None)
check("nonpositive CAGR endpoint remains missing",m.cagr3(-1,1) is None)
check("missing input remains missing",m.fcf(None,2) is None)

# HTTP body decoding regression: the first GitHub R10B run failed because the SEC
# returned compressed JSON and the client attempted to UTF-8 decode compressed bytes.
import gzip, json, zlib
payload=json.dumps({"facts":{"us-gaap":{}}}).encode("utf-8")
check("plain HTTP body decoded",m.decode_http_body(payload,"")==payload)
check("gzip HTTP body decoded",m.decode_http_body(gzip.compress(payload),"gzip")==payload)
check("deflate HTTP body decoded",m.decode_http_body(zlib.compress(payload),"deflate")==payload)

print(f"PASS={PASS} FAIL={FAIL}")
if FAIL:raise SystemExit(1)
print("R10B SYNTHETIC RECOVERY TESTS PASSED")
