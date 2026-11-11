"""Recompute stale buyback/SBC ratios after DATA15-17 source recovery; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='cbadf0355af9b69069bcdd78a70dc26939401b450a2efdfba276d9ab8d4dafe2'
PROOF='d421efd88ffe0365353b990a878fbc1a54db8351127eb0b3f3ac99901a098765'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'BR03 policy hash mismatch')
    from enrich_br03_capital_return import derive_buyback_accretion,row_status
    rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    targets={'CEG':(400000000,385000000),'MET':(2883000000,131000000),'JPM':(31591000000,3614000000),'USB':(489000000,235000000)}
    for ticker,(buyback,sbc) in targets.items():
        selected=[r for r in rows if r['ticker']==ticker];require(len(selected)==1,'ticker mismatch');r=selected[0]
        require(float(r['annual_buyback'])==buyback and float(r['annual_sbc'])==sbc,'source values changed')
        require(r['annual_buyback_adsh']==r['annual_adsh'],'accession mismatch')
        require(all(r[k] and int(float(r[k]))==20251231 for k in ['annual_period','annual_buyback_date','annual_sbc_date']),'period mismatch')
        require(r['buyback_accretion']=='' and r['br03_status']=='PARTIAL','target already populated')
        value,flags=derive_buyback_accretion(buyback,sbc)
        require(not flags and value>0,'unexpected derivation flags')
        r['buyback_accretion']=repr(value)
        r['br03_status']=row_status(value,r['payout_ratio'],buyback,r['annual_dividends_paid'])
        require(r['br03_status']=='PRESENT','unexpected status')
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require({(x['ticker'],x['field']) for x in ledger}=={(t,k) for t in targets for k in ['buyback_accretion','br03_status']},'scope mismatch')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data18/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'src/enrich_br03_capital_return.py').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data19';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data19_sbc_dependents_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,other_rows_preserved=500,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA19_REPORT='+json.dumps(report))
if __name__=='__main__':main()
