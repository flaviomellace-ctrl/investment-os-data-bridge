"""Suppress IP ratios crossing continuing/discontinued-operation bases; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='347e6eacaf9cb8d5837a90c312be9881b99bcbd14a337c18c47b6843e09df48b'
PROOF='114be207d1cf74102e88eb8be568dae30bfdda0e578a5e50ec96f2c71acce2df'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    selected=[r for r in rows if r['ticker']=='IP'];require(len(selected)==1,'ticker mismatch');r=selected[0]
    require(r['annual_adsh']==ev['accession'],'filing mismatch')
    require(float(r['annual_revenue'])==23634000000 and float(r['prior_revenue'])==18619000000,'source inputs changed')
    require([x['value'] for x in ev['revenue_facts']]==[23634000000,15835000000,16033000000],'comparatives changed')
    require(sha(ev['income_statement_text'].encode())==ev['income_statement_sha256'],'statement mismatch')
    require(float(r['annual_net_income'])==-3516000000 and float(r['annual_operating_cash_flow'])==1698000000 and float(r['annual_capex'])==1857000000,'mixed-basis inputs changed')
    for k in ['revenue_yoy','net_margin','fcf_margin']:
        require(r[k]!='','target already suppressed');r[k]=''
    require(r['data_quality_flags']=='OK' and r['data_status']=='PRESENT','unexpected descriptive status')
    r['data_quality_flags']='IP_MIXED_CONTINUING_DISCONTINUED_BASIS';r['data_status']='PARTIAL'
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require({(x['ticker'],x['field']) for x in ledger}=={('IP',k) for k in ['revenue_yoy','net_margin','fcf_margin','data_quality_flags','data_status']},'scope mismatch')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data21/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/ip_mixed_basis_source.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data23';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine)
        if row['ticker']=='IP':
            require(row['data_quality_flags']=='IP_MIXED_CONTINUING_DISCONTINUED_BASIS','basis guard missing')
            require(c['fcf_margin'] is None and c['net_margin'] is None,'suppressed ratio leaked')
            c['reinvestment_rate']=None  # capex includes discontinued operations; revenue does not.
        score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data23_ip_basis_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,research_adapter_overrides={'IP':['reinvestment_rate']},override_reason='capex/revenue basis mismatch; frozen engine unchanged',other_rows_preserved=503,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA23_REPORT='+json.dumps(report))
if __name__=='__main__':main()
