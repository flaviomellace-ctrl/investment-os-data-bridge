"""Pinned MET/JPM SBC and IP/MET/CVX diluted shares amendment; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='f6fee043504a2ae5389792cf7e9abd33b64722c492129b0d61562c0ff3dd233e'
PROOF='ebf8af651c9d84ff7a9156fd3e8dd93cd76b06857bdaeab5024fc9f693da066e'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    by={r['ticker']:r for r in rows};allowed=set()
    targets={('MET','annual_sbc'):131000000,('JPM','annual_sbc'):3614000000,('IP','annual_diluted_shares'):505700000,('MET','annual_diluted_shares'):673300000,('CVX','annual_diluted_shares'):1856000000}
    for (ticker,field),value in targets.items():
        row=by[ticker];ob=next(x for x in ev['observations'] if x['ticker']==ticker and x['field']==field);fact=ob['facts'][0]
        require(row['annual_adsh']==ob['accession'] and row[field]=='','filing or target mismatch')
        require(fact['status']=='INLINE_VALUE_AND_TABLE_VERIFIED' and float(fact['value'])==value and fact['start']==['2025-01-01'],'source mismatch')
        require(sha(fact['table_text'].encode())==fact['table_sha256'],'table mismatch')
        for k,v in [(field,repr(float(value))),(field+'_tag',fact['concept']),(field+'_date','20251231.0')]:row[k]=v;allowed.add((ticker,k))
    for ticker in ['MET','JPM']:
        row=by[ticker];allowed.add((ticker,'sbc_to_revenue'))
        row['sbc_to_revenue']=repr(float(row['annual_sbc'])/float(row['annual_revenue'])) if row['annual_revenue'] and float(row['annual_revenue'])!=0 else ''
    core=['annual_'+x for x in ['revenue','net_income','assets','equity','operating_cash_flow','diluted_shares']]
    for ticker in ['IP','MET','CVX']:
        row=by[ticker]
        # Prior/three-year shares are still missing: growth cannot be manufactured.
        require(row['prior_diluted_shares']=='' and row['fy_minus_3_diluted_shares']=='','historical inputs changed')
        require(all(row[k]=='' for k in ['diluted_shares_yoy','share_change','fcf_per_share_cagr3']),'unexpected growth value')
        flags=[x for x in row['data_quality_flags'].split(';') if x not in ['MISSING_DILUTED_SHARES','OK','']]
        updates={'core_metric_coverage_pct':repr(round(100*sum(bool(row[k]) for k in core)/6,1)),'extended_metric_coverage_pct':repr(round(100*sum(bool(row[k]) for k in core+['annual_capex','annual_debt'])/8,1)),'data_quality_flags':';'.join(flags) if flags else 'OK','data_status':'PARTIAL' if flags else 'PRESENT'}
        for k,v in updates.items():row[k]=v;allowed.add((ticker,k))
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require(all((x['ticker'],x['field']) in allowed for x in ledger),'scope mismatch')
    require(len(ledger)==28,'unexpected change count')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data15/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/remaining_gap_primary_scan.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data16';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data16_missing_facts_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,other_rows_preserved=500,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA16_REPORT='+json.dumps(report))
if __name__=='__main__':main()
