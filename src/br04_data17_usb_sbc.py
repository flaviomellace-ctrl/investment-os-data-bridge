"""Pinned USB SBC from incorporated EX-13 amendment; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='7ac5d1928ad9198ca1774d355927148c7d28dd267e12058d0d4e96ba315f5d02'
PROOF='bd683c6e4d332f28d5000c05769ad99848ab3ecfb737cb882004d8c773442bc7'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    selected=[r for r in rows if r['ticker']=='USB'];require(len(selected)==1,'ticker identity mismatch');row=selected[0]
    require(row['annual_adsh']==ev['accession'] and row['annual_sbc']=='','filing or target mismatch')
    require(ev['status']=='INLINE_VALUE_CONTEXT_UNIT_AND_NARRATIVE_VERIFIED' and ev['value']==235000000 and ev['start']=='2025-01-01' and ev['end']=='2025-12-31' and ev['unit']=='USD' and not ev['dimensions'],'source mismatch')
    require(sha(ev['paragraph'].encode())==ev['paragraph_sha256'],'narrative mismatch')
    require(int(float(row['annual_period']))==20251231,'period mismatch')
    row['annual_sbc']='235000000.0';row['annual_sbc_tag']=ev['concept'];row['annual_sbc_date']='20251231.0'
    row['sbc_to_revenue']=repr(float(row['annual_sbc'])/float(row['annual_revenue'])) if row['annual_revenue'] and float(row['annual_revenue'])!=0 else ''
    allowed={'annual_sbc','annual_sbc_tag','annual_sbc_date','sbc_to_revenue'}
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require(all(x['ticker']=='USB' and x['field'] in allowed for x in ledger),'scope mismatch')
    require(len(ledger)==3+int(bool(row['sbc_to_revenue'])),'unexpected change count')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data16/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/usb_ex13_sbc_source.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data17';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data17_usb_sbc_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,other_rows_preserved=503,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA17_REPORT='+json.dumps(report))
if __name__=='__main__':main()
