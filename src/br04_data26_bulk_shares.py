"""Bulk source-verified diluted shares; retain IP basis quarantine; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='5b89307896a25ae77c10cc18d57f6b604064dc700346c791ae67e8a7105beb83'
PROOF='f59b023a671561ad8f9884fccbc6cb9bf5749c54c473d06302678eb7958de04a'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows];by={r['ticker']:r for r in rows}
    require(len(rows)==len(by)==504 and len(header)==285,'shape mismatch')
    receipts={str(int(x['cik'])):x for x in ev['receipts']};allowed=set();changed_inputs={}
    for ob in ev['observations']:
        if ob['status']!='EXACT_ACCESSION_PERIOD_UNITS_NO_LATER_CONFLICT':continue
        r=by[ob['ticker']];field=ob['field'];prefix=field.removesuffix('diluted_shares');f=ob['fact']
        require(prefix in ['annual_','fy_minus_1_','fy_minus_2_','fy_minus_3_'],'unexpected field')
        require(r[field]=='' and ob['unit']=='shares' and ob['concept']=='WeightedAverageNumberOfDilutedSharesOutstanding','target/concept mismatch')
        require(str(int(float(r['cik'])))==str(int(ob['cik'])),'CIK mismatch')
        require(ob['source_sha256']==receipts[str(int(ob['cik']))]['sha256'],'receipt mismatch')
        date=str(int(float(r[prefix+'period'])));filed=str(int(float(r[prefix+'filed'])))
        require(f['accn']==r[prefix+'adsh'] and f['end'].replace('-','')==date and f['filed'].replace('-','')==filed,'filing/period mismatch')
        require(f['form'] in ['10-K','10-K/A'] and f['fp']=='FY' and 0<f['val']<10**13,'fact mismatch')
        if prefix=='fy_minus_1_' and r['prior_diluted_shares']:
            require(float(r['prior_diluted_shares'])==f['val'],'prior share alias conflicts with selected source')
        for k,v in [(field,repr(float(f['val']))),(field+'_tag',ob['concept']),(field+'_date',date+'.0')]:
            require(r[k]=='','provenance already populated');r[k]=v;allowed.add((r['ticker'],k))
        changed_inputs.setdefault(r['ticker'],set()).add(prefix)
        if prefix=='fy_minus_1_' and not r['prior_diluted_shares']:
            for k,v in [('prior_diluted_shares',r[field]),('prior_diluted_shares_date',r[field+'_date'])]:
                r[k]=v;allowed.add((r['ticker'],k))
    core=['annual_'+k for k in ['revenue','net_income','assets','equity','operating_cash_flow','diluted_shares']]
    for ticker,prefixes in changed_inputs.items():
        r=by[ticker]
        if prefixes & {'annual_','fy_minus_1_'}:
            if r['annual_diluted_shares'] and r['prior_diluted_shares']:
                growth=float(r['annual_diluted_shares'])/float(r['prior_diluted_shares'])-1.0
                for k in ['diluted_shares_yoy','share_change']:r[k]=repr(growth);allowed.add((ticker,k))
                flags=[x for x in r['br03_flags'].split(';') if x and x not in ['SHARE_ISSUANCE','SHARE_COUNT_DISCONTINUITY']]
                if growth>0.05:flags.append('SHARE_ISSUANCE')
                if abs(growth)>0.50:flags.append('SHARE_COUNT_DISCONTINUITY')
                r['br03_flags']=';'.join(flags);allowed.add((ticker,'br03_flags'))
        if prefixes & {'annual_','fy_minus_3_'}:
            def fcf_ps(p):
                keys=[p+'operating_cash_flow',p+'capex',p+'diluted_shares']
                if any(not r[k] for k in keys):return None
                ocf,capex,shares=[float(r[k]) for k in keys]
                return (ocf-abs(capex))/shares if shares>0 else None
            now,old=fcf_ps('annual_'),fcf_ps('fy_minus_3_')
            r['fcf_per_share_cagr3']=repr((now/old)**(1.0/3.0)-1.0) if now is not None and old is not None and now>0 and old>0 else ''
            allowed.add((ticker,'fcf_per_share_cagr3'))
        if 'annual_' in prefixes:
            flags=[x for x in r['data_quality_flags'].split(';') if x not in ['MISSING_DILUTED_SHARES','OK','']]
            updates={'core_metric_coverage_pct':repr(round(100*sum(bool(r[k]) for k in core)/6,1)),'extended_metric_coverage_pct':repr(round(100*sum(bool(r[k]) for k in core+['annual_capex','annual_debt'])/8,1)),'data_quality_flags':';'.join(flags) if flags else 'OK','data_status':'PARTIAL' if flags else 'PRESENT'}
            for k,v in updates.items():r[k]=v;allowed.add((ticker,k))
    require(len(changed_inputs)==111,'unexpected target universe')
    require(sum(1 for o in ev['observations'] if o['status']=='EXACT_ACCESSION_PERIOD_UNITS_NO_LATER_CONFLICT')==379,'source scope changed')
    require(by['IP']['data_quality_flags']=='IP_MIXED_CONTINUING_DISCONTINUED_BASIS','IP guard lost')
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require(all((x['ticker'],x['field']) in allowed for x in ledger),'scope mismatch')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    import base64,zlib
    source=(ROOT/'data/research/br04-data23/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=zlib.decompress(base64.b64decode((ROOT/'docs/evidence/bulk_share_sources.json.zlib.b64').read_bytes()))
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data26';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
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
    report=dict(schema='br04_data26_bulk_shares_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,research_adapter_overrides={'IP':['reinvestment_rate']},override_reason='capex/revenue basis mismatch; frozen engine unchanged',other_rows_preserved=504-len({x["ticker"] for x in ledger}),transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA26_REPORT='+json.dumps(report))
if __name__=='__main__':main()
