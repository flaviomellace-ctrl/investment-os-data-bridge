"""Pinned CEG pretax SBC amendment; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='bc47a98f342a69ecf6017937d7e713fb2733ab0de4057debe346fc268ccec0ea'
PROOF='cfe52447b70979f09a53d1b31513e5c442b914a2a807a8134c5dfd96eb061881'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);require(ev['expense_usd']==385000000 and ev['concept']=='AllocatedShareBasedCompensationExpense','expense basis mismatch')
    rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    row=next(x for x in rows if x['ticker']=='CEG');require(row['annual_adsh']==ev['accession'] and row['annual_sbc']=='','filing or target mismatch')
    require(float(row['annual_revenue'])==ev['revenue_usd'],'revenue basis mismatch')
    row.update(annual_sbc='385000000.0',annual_sbc_tag=ev['concept'],annual_sbc_date='20251231.0',sbc_to_revenue=repr(385000000/float(row['annual_revenue'])))
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require({(x['ticker'],x['field']) for x in ledger}=={('CEG',k) for k in ['annual_sbc','annual_sbc_tag','annual_sbc_date','sbc_to_revenue']},'scope mismatch')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data14/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/ceg_sbc_source_investigation.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data15';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data15_ceg_sbc_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,other_rows_preserved=503,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA15_REPORT='+json.dumps(report))
if __name__=='__main__':main()
