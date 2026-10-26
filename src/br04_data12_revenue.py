"""Scoped total-revenue research policy for CEG/WELL; no release approval."""
import argparse,csv,io,json,math
from collections import Counter
from decimal import Decimal
from pathlib import Path
try:
    from .br04_data11_mcd import ROOT,sha,require,PROOF_SHA,RECEIPT_SHA
except ImportError:
    from br04_data11_mcd import ROOT,sha,require,PROOF_SHA,RECEIPT_SHA
INPUT_SHA='c856d8af683e1b4ca8d21ba3c8258b7a19714301964209f9176893728a33b486'
COMPANIES={'CEG':(1868275,'0001868275-26-000032','2026-02-24'),'WELL':(766704,'0000766704-26-000010','2026-02-12')}
CORE=['annual_'+s for s in ['revenue','net_income','assets','equity','operating_cash_flow','diluted_shares']]
def number(x):
    try:
        n=float(x);return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None

def verify_archive(directory,proof_bytes):
    from br04_primary_filing import Sources
    require(sha(proof_bytes)==PROOF_SHA,'proof hash mismatch')
    sources=Sources(directory,RECEIPT_SHA,38277084865,'b99ecc7a8a9d430b151f7da69919ef67b79d81fb')
    verified=[]
    for ev in json.loads(proof_bytes):
        t=ev.get('ticker')
        if t not in COMPANIES:continue
        f=ev['source_fact']; cik,acc,cutoff=COMPANIES[t]
        body=(Path(directory)/f['source_file']).read_bytes()
        require(sha(body)==f['source_sha256'],'companyfacts hash differs')
        facts=json.loads(body);require(str(facts['cik']).lstrip('0')==str(cik),'CIK differs')
        candidates=[v for v in facts['facts']['us-gaap']['Revenues']['units']['USD'] if v.get('form')=='10-K' and v.get('start')==f['start'] and v.get('end')==f['end'] and v.get('filed','9999')<=cutoff]
        require(candidates and {v['val'] for v in candidates}=={f['val']},'revenue missing or conflicting by cutoff')
        require(any(all(v.get(k)==f[k] for k in ['accn','start','end','val','filed']) for v in candidates),'selected source identity differs')
        if 'primary' in ev:
            p=ev['primary'];fact=sources.one(acc,cik,'Revenues',f['end'],f['start']);fresh=sources.table(fact,p['caption_required'])
            require(fresh==p and Decimal(fact['value'])==Decimal(f['val']),'primary proof differs')
        verified.append({'ticker':t,'year':f['end'][:4],'revenue':f['val'],'source_accession':f['accn'],'primary_table_verified':'primary' in ev,'companyfacts_verified':True})
    require(len(verified)==8,'expected eight annual observations')
    return {'schema':'br04_data12_archive_verification_v1','receipt_sha256':RECEIPT_SHA,'proof_sha256':PROOF_SHA,'observations':verified,'fresh_sec_fetch':False,'candidate_promoted':False,'economic_clearance':False,'buy_add_allowed':False}

def amend(data,proof_bytes):
    require(sha(data)==INPUT_SHA,'input hash mismatch');require(sha(proof_bytes)==PROOF_SHA,'proof hash mismatch')
    reader=csv.DictReader(io.StringIO(data.decode()));header=reader.fieldnames;rows=list(reader);original=[dict(r) for r in rows]
    require(len(rows)==504 and len(header)==285 and len({r['ticker'] for r in rows})==504,'shape mismatch')
    by={r['ticker']:r for r in rows};provenance=[]
    def put(row,key,value):
        require(key in header,'unknown column')
        if isinstance(value,str):row[key]=value;return
        old=number(row[key])
        if value is not None and old is not None and math.isclose(old,value,rel_tol=1e-13,abs_tol=1e-15):return
        row[key]='' if value is None else repr(float(value))
    def ratio(a,b):return None if a is None or b in [None,0] else a/b
    for t,(cik,acc,cutoff) in COMPANIES.items():
        row=by[t];require(row['annual_adsh']==acc,'annual filing differs')
        observations=[e for e in json.loads(proof_bytes) if e.get('ticker')==t]
        require({e['source_fact']['end'] for e in observations}=={f'{y}-12-31' for y in range(2022,2026)},'annual series incomplete')
        for ev in observations:
            f=ev['source_fact'];year=int(f['end'][:4]);require(f['concept']=='Revenues' and f['start']==f'{year}-01-01' and f['filed']<=cutoff and f['val']>0,'invalid annual observation')
            prefixes=['annual_'] if year==2025 else ['prior_','fy_minus_1_'] if year==2024 else [f'fy_minus_{2025-year}_']
            for pre in prefixes:
                put(row,pre+'revenue',f['val'])
                if pre+'revenue_tag' in header:put(row,pre+'revenue_tag','Revenues')
                put(row,pre+'revenue_date',float(f['end'].replace('-','')))
                provenance.append({'ticker':t,'field':pre+'revenue','source_accession':f['accn'],'source_file':f['source_file'],'source_sha256':f['source_sha256'],'period_start':f['start'],'period_end':f['end'],'concept':'Revenues','policy':'CONSOLIDATED_TOTAL_REVENUE','basis':'LATEST_COMPARATIVE_AVAILABLE_BY_ANNUAL_FILING_CUTOFF','row_level_historical_accession_preserved':True})
        n=lambda k:number(row[k]);rv=n('annual_revenue')
        for key,num in [('operating_margin','annual_operating_income'),('net_margin','annual_net_income'),('fcf_margin','annual_fcf'),('sbc_to_revenue','annual_sbc')]:put(row,key,ratio(n(num),rv))
        put(row,'revenue_yoy',rv/n('prior_revenue')-1)
        put(row,'revenue_cagr3',(rv/n('fy_minus_3_revenue'))**(1/3)-1)
        margins=[]
        for pre in ['annual_','fy_minus_1_','fy_minus_2_','fy_minus_3_']:
            margin=ratio(n(pre+'operating_income'),n(pre+'revenue'));put(row,pre+'operating_margin_history',margin)
            if margin is not None:margins.append(margin)
        mean=sum(margins)/len(margins) if margins else None
        put(row,'operating_margin_std_4y',math.sqrt(sum((m-mean)**2 for m in margins)/len(margins)) if len(margins)>=2 else None)
        put(row,'operating_margin_range_4y',max(margins)-min(margins) if len(margins)>=2 else None)
        put(row,'core_metric_coverage_pct',round(100*sum(n(k) is not None for k in CORE)/6,1))
        put(row,'extended_metric_coverage_pct',round(100*sum(n(k) is not None for k in CORE+['annual_capex','annual_debt'])/8,1))
        flags=[f for f in row['data_quality_flags'].split(';') if f not in ['OK','MISSING_REVENUE','']]
        put(row,'data_quality_flags',';'.join(flags) if flags else 'OK')
        put(row,'data_status','PARTIAL' if flags else 'PRESENT')
    changes=[{'ticker':a['ticker'],'field':k,'before':a[k],'after':b[k]} for a,b in zip(original,rows) for k in header if a[k]!=b[k]]
    require(all(c['ticker'] in COMPANIES and header.index(c['field'])<212 for c in changes),'scope violation')
    out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=header);w.writeheader();w.writerows(rows);output=out.getvalue().encode()
    report={'schema':'br04_data12_revenue_amendment_v1','input_sha256':sha(data),'candidate_sha256':sha(output),'proof_sha256':PROOF_SHA,'policy':'CONSOLIDATED_TOTAL_REVENUE_CEG_WELL_ONLY','changes':changes,'changed_cells':len(changes),'unchanged_other_rows':502,'br04_fields_preserved':True,'field_provenance':provenance,'prior_approvals_inherited':False,'candidate_promoted':False,'economic_clearance':False,'buy_add_allowed':False}
    return output,report

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive');p.add_argument('--engine',action='store_true');args=p.parse_args()
    proof=(ROOT/'data/research/br04-data10/prior_rc1_proofs.json').read_bytes();data=(ROOT/'data/research/br04-data11/RESEARCH_NOT_PROMOTED.csv').read_bytes()
    output,report=amend(data,proof);dest=ROOT/'data/research/br04-data12';dest.mkdir(parents=True,exist_ok=True)
    if args.archive:(dest/'archive_verification.json').write_text(json.dumps(verify_archive(args.archive,proof),indent=2)+'\n')
    (dest/'RESEARCH_NOT_PROMOTED.csv').write_bytes(output);(dest/'amendment.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.engine:
        from br04_data09_preflight import load_frozen_engine,derive
        engine,md5=load_frozen_engine();confidence=Counter();count=0;ios_count=0
        for row in csv.DictReader(io.StringIO(output.decode())):
            c=derive(row,engine);score,cov,detail,_=engine.bqs(c)
            confidence[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
            if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
                value,_=engine.ios(c,score,cov);ios_count+=value is not None
            count+=1
        require(count==504,'engine row count differs')
        er={'schema':'br04_data12_engine_compatibility_v1','candidate_sha256':sha(output),'engine_md5':md5,'rows_processed':count,'exceptions':0,'confidence_counts':dict(confidence),'ios_computable_rows':ios_count,'prior_approvals_inherited':False,'candidate_promoted':False,'economic_clearance':False,'buy_add_allowed':False}
        (dest/'engine_compatibility.json').write_text(json.dumps(er,indent=2)+'\n');print(json.dumps(er))
    print(json.dumps({k:v for k,v in report.items() if k not in ['changes','field_provenance']}))
if __name__=='__main__':main()
