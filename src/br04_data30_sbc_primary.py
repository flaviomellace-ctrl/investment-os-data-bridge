"""Apply 35 primary-confirmed SBC expenses; research only."""
import csv,io,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
INPUT='32b60915d9da5d6f43b10187eabee47b50710954118e64ae80161437e43d3b5b'
PROOF='7c58cb3e57bf01a6bddf4e0acbebae716c46f9430a9ff0b941ab92c41666629d'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def amend(data,proof):
    require(sha(data)==INPUT,'candidate hash mismatch');require(sha(proof)==PROOF,'proof hash mismatch')
    ev=json.loads(proof);rd=csv.DictReader(io.StringIO(data.decode()));header=rd.fieldnames;rows=list(rd);before=[dict(x) for x in rows];by={r['ticker']:r for r in rows};allowed=set()
    require(len(rows)==len(by)==504 and len(header)==285,'shape mismatch')
    require(len(ev['observations'])==35,'source scope mismatch')
    for ob in ev['observations']:
        r=by[ob['ticker']];field=ob['field'];p='annual_' if field=='annual_sbc' else 'fy_minus_2_';facts=ob['facts'];f=facts[0]['fact'];tag=facts[0]['concept']
        require(field=='annual_sbc','unexpected field')
        require(ob['primary']['disposition']=='PRIMARY_EXPENSE_SCOPE_CONFIRMED_PENDING_APPLICATION' and ob['primary']['applied_value']==f['val'],'primary scope mismatch')
        require(f['accn'].replace('-','') in ob['primary']['url'],'primary filing mismatch')
        require(len({x['fact']['val'] for x in facts})==1 and f['val']>0,'ambiguous value')
        require(str(int(float(r['cik'])))==str(int(ob['receipt']['cik'])),'CIK mismatch')
        require(r[p+'adsh']==f['accn'] and str(int(float(r[p+'period'])))==f['end'].replace('-','') and str(int(float(r[p+'filed'])))==f['filed'].replace('-',''),'filing mismatch')
        for k,v in [(field,repr(float(f['val']))),(field+'_tag',tag),(field+'_date',f['end'].replace('-','')+'.0')]:
            require(r[k]=='','target or provenance already populated');r[k]=v;allowed.add((r['ticker'],k))
        if field!='annual_sbc':continue
        require(r['sbc_to_revenue']=='' and r['buyback_accretion']=='','dependent metric already populated')
        r['sbc_to_revenue']=repr(float(r['annual_sbc'])/float(r['annual_revenue'])) if r['annual_revenue'] and float(r['annual_revenue'])!=0 else ''
        allowed.add((r['ticker'],'sbc_to_revenue'))
        if r['annual_buyback']:
            require(float(r['annual_buyback'])>=0,'buyback sign anomaly')
            require(r['annual_buyback_date']==r['annual_sbc_date'] and r['annual_buyback_adsh']==r['annual_adsh'],'buyback period/filing mismatch')
            r['buyback_accretion']=repr(float(r['annual_buyback'])/float(r['annual_sbc']))
            allowed.add((r['ticker'],'buyback_accretion'))
        acc=bool(r['buyback_accretion']);payout=bool(r['payout_ratio']);raw_known=bool(r['annual_buyback']) or bool(r['annual_dividends_paid'])
        r['br03_status']='PRESENT' if acc and payout else 'PARTIAL' if acc or payout or raw_known else 'MISSING';allowed.add((r['ticker'],'br03_status'))
    ledger=[dict(ticker=a['ticker'],field=k,before=a[k],after=b[k]) for a,b in zip(before,rows) for k in header if a[k]!=b[k]]
    require(all((x['ticker'],x['field']) in allowed for x in ledger),'scope mismatch')
    require(len({x['ticker'] for x in ledger})==35,'ticker scope mismatch')
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=header);w.writeheader();w.writerows(rows)
    return s.getvalue().encode(),ledger

def main():
    from br04_data14_market_refresh import CURRENT_SHA,verify_transport
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';baseline=current.read_bytes();require(sha(baseline)==CURRENT_SHA,'current base changed')
    source=(ROOT/'data/research/br04-data28/RESEARCH_NOT_PROMOTED.csv').read_bytes();proof=(ROOT/'docs/evidence/sbc26_source.json').read_bytes()
    data,ledger=amend(source,proof)
    # Reject tampering and double application against real inputs.
    for a,b in [(source+b' ',proof),(source,proof+b' '),(data,proof)]:
        try:amend(a,b)
        except ValueError:pass
        else:raise ValueError('tamper accepted')
    out=ROOT/'data/research/br04-data30';out.mkdir(parents=True,exist_ok=True);candidate=out/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
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
    report=dict(schema='br04_data30_sbc_primary_v1',input_sha256=INPUT,candidate_sha256=sha(data),proof_sha256=PROOF,current_base_sha256=CURRENT_SHA,changes=ledger,research_adapter_overrides={'IP':['reinvestment_rate']},override_reason='capex/revenue basis mismatch; frozen engine unchanged',other_rows_preserved=469,excluded_facts={'GE':'325m is after-tax; preserve missing pretax SBC','AES':'14m covers only other award programs; preserve missing total'},transport=transport,engine_md5=md5,rows_processed=n,exceptions=0,confidence_counts=dict(counts),ios_computable_rows=ios,overall_passed=True,historical_approvals_transferred=False,candidate_promoted=False,economic_clearance=False,buy_add_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('DATA30_REPORT='+json.dumps(report))
if __name__=='__main__':main()
