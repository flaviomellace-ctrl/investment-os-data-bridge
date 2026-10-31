"""CMCSA statement-component liabilities with independent balance-sheet cross-check; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='dcfce67f685fecb205b2b0028a759bc1e29bed61745b2cd34904d4dba0435a5e'
PROOF='f4a3535e1317a444d6759cba0a0e3e412599024ac6d34a77c3bdebb7b6f3cb06'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    selected=[r for r in rows if r['ticker']=='CMCSA'];require(len(selected)==1,'ticker mismatch');r=selected[0]
    require(r['annual_adsh']==ev['accession'] and int(float(r['annual_period']))==20251231,'filing mismatch')
    require(r['total_liabilities']=='' and r['total_liabilities_components']=='','target not empty')
    fs=ev['facts'];require(sum(f['value'] for f in fs[:4])==ev['total_liabilities']==175256000000,'components do not reconcile')
    require(fs[7]['value']-fs[6]['value']-fs[4]['value']==ev['total_liabilities'],'equity bridge mismatch')
    require(float(r['total_liabilities_and_equity'])==fs[7]['value'] and float(r['annual_equity'])==fs[5]['value'],'balance sheet inputs changed')
    r['total_liabilities']=str(ev['total_liabilities'])
    r['total_liabilities_components']=';'.join(f['concept'].split(':')[-1]+'='+str(f['value']) for f in fs[:4])
    flags=r['br04_flags'].split(';');require('FSDS_FACE_ONLY' in flags,'unexpected source flags')
    flags.remove('FSDS_FACE_ONLY');flags.append('PRIMARY_FILING_LIABILITIES_COMPONENTS');r['br04_flags']=';'.join(sorted(set(flags)))
    # Preserve old closure/perimeter flags: parent-only equity does not close the balance sheet.
    require('BS_CLOSURE_FAILED' in r['br04_flags'] and r['ios_leverage_indeterminate']=='true','unexpected clearance')
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require({(x['ticker'],x['field']) for x in ledger}=={('CMCSA',k) for k in ['total_liabilities','total_liabilities_components','br04_flags']},'scope mismatch')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data19/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/cmcsa_liabilities_source.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data21';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data21_cmcsa_liabilities_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,other_rows_preserved=503,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA21_REPORT='+json.dumps(report))
if __name__=='__main__':main()
