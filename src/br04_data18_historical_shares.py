"""Pinned IP/MET/CVX historical diluted shares amendment; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='c1e65bddc5161dbf6ef11779a7acb5ed1b5869258b1c3bde3a12cb1e67e40966'
PROOF='b733db8ccfb7ce94cf13d65524464a4f141d748d7d2832bd3eaa96853a51a540'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows]
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    by={r['ticker']:r for r in rows};allowed=set()
    expected={'IP':[354200000,349100000,367000000],'MET':[711100000,762300000,808900000],'CVX':[1817000000,1880000000,1940000000]}
    require(len(ev['observations'])==9,'observation count mismatch')
    for ticker,values in expected.items():
        row=by[ticker]
        for i,value in enumerate(values,1):
            pre=f'fy_minus_{i}_';field=pre+'diluted_shares';matches=[x for x in ev['observations'] if x['ticker']==ticker and x['field']==field]
            require(len(matches)==1,'proof identity mismatch');ob=matches[0];fact=ob['fact'];year=2025-i
            require(fact['accn']==row[pre+'adsh'] and fact['val']==value and fact['start']==f'{year}-01-01' and fact['end']==f'{year}-12-31' and fact['form']=='10-K' and ob['unit']=='shares','source mismatch')
            date=str(int(float(row[pre+'period'])));require(date==f'{year}1231','period mismatch')
            for k,v in [(field,repr(float(value))),(field+'_tag',ob['concept']),(field+'_date',date+'.0')]:
                require(row[k]=='','historical field already populated');row[k]=v;allowed.add((ticker,k))
        for k,v in [('prior_diluted_shares',row['fy_minus_1_diluted_shares']),('prior_diluted_shares_date',row['fy_minus_1_diluted_shares_date'])]:
            require(row[k]=='','prior already populated');row[k]=v;allowed.add((ticker,k))
        growth=float(row['annual_diluted_shares'])/float(row['prior_diluted_shares'])-1.0
        for k in ['diluted_shares_yoy','share_change']:
            require(row[k]=='','growth already populated');row[k]=repr(growth);allowed.add((ticker,k))
        flags=[x for x in row['br03_flags'].split(';') if x and x not in ['SHARE_ISSUANCE','SHARE_COUNT_DISCONTINUITY']]
        if growth>0.05:flags.append('SHARE_ISSUANCE')
        if abs(growth)>0.50:flags.append('SHARE_COUNT_DISCONTINUITY')
        row['br03_flags']=';'.join(flags);allowed.add((ticker,'br03_flags'))
        # Follow BR01/02 CAGR semantics: absent capex is not zero; endpoints must be positive.
        def per_share(pre):
            keys=[pre+'operating_cash_flow',pre+'capex',pre+'diluted_shares']
            if any(not row[k] for k in keys):return None
            ocf,capex,shares=map(lambda k:float(row[k]),keys)
            return (ocf-abs(capex))/shares if shares>0 else None
        now,old=per_share('annual_'),per_share('fy_minus_3_')
        require(row['fcf_per_share_cagr3']=='','CAGR already populated')
        if now is not None and old is not None and now>0 and old>0:
            row['fcf_per_share_cagr3']=repr((now/old)**(1.0/3.0)-1.0)
        allowed.add((ticker,'fcf_per_share_cagr3'))
    require(all(by[t]['fcf_per_share_cagr3']=='' for t in ['IP','MET']),'missing inputs became zero')
    require('SHARE_ISSUANCE' in by['IP']['br03_flags'].split(';'),'issuance flag missing')
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require(all((x['ticker'],x['field']) in allowed for x in ledger),'scope mismatch')
    require(len(ledger)==41,'unexpected change count')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data17/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/historical_shares_source.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data18';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    transport=verify_transport(data,out,split_file(source=candidate,output_dir=out,url_base=None))
    engine,md5=load_frozen_engine();counts=Counter();n=0;ios=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c);counts[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios+=value is not None
        n+=1
    require(n==504 and current.read_bytes()==baseline and candidate.read_bytes()==data,'runtime mutation')
    report=dict(schema='br04_data18_historical_shares_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,other_rows_preserved=501,transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA18_REPORT='+json.dumps(report))
if __name__=='__main__':main()
