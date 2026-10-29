"""Acquire missing share evidence in one pass; no candidate mutation or clearance."""
import csv,datetime as dt,gzip,hashlib,io,json,os,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INPUT='5b89307896a25ae77c10cc18d57f6b604064dc700346c791ae67e8a7105beb83'
TAG='WeightedAverageNumberOfDilutedSharesOutstanding'
def select(facts,accession,end,filed):
    end_date=dt.date.fromisoformat(end)
    matching=[]
    for f in facts:
        if f.get('accn')!=accession or f.get('end')!=end or f.get('filed')!=filed or f.get('form') not in ('10-K','10-K/A') or f.get('fp')!='FY':continue
        try:days=(end_date-dt.date.fromisoformat(f['start'])).days
        except (KeyError,ValueError):continue
        if 330<=days<=380:matching.append(f)
    if not matching:return None,'NO_EXACT_ANNUAL_FACT'
    if len({(f['start'],f['val']) for f in matching})!=1:return None,'AMBIGUOUS_EXACT_FACTS'
    f=matching[0]
    if not isinstance(f['val'],(int,float)) or not 0<f['val']<10**13:return None,'INVALID_VALUE'
    later=[x for x in facts if x.get('start')==f['start'] and x.get('end')==end and x.get('form') in ('10-K','10-K/A') and x.get('filed','')>=filed]
    if any(x['val']!=f['val'] for x in later):return None,'LATER_RESTATEMENT_OR_SPLIT_REVIEW'
    return f,'EXACT_ACCESSION_PERIOD_UNITS_NO_LATER_CONFLICT'
def date(v):return dt.datetime.strptime(str(int(float(v))),'%Y%m%d').date().isoformat()
def main():
    raw=(ROOT/'data/research/br04-data23/RESEARCH_NOT_PROMOTED.csv').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==INPUT
    rows=list(csv.DictReader(io.StringIO(raw.decode())));out=ROOT/'data/research/br04-data25';out.mkdir(parents=True,exist_ok=True);(out/'raw').mkdir(exist_ok=True)
    email=os.environ.get('SEC_CONTACT_EMAIL','').strip()
    if not email:raise ValueError('SEC contact required')
    targets={};observations=[]
    for r in rows:
        for prefix in ('annual_','fy_minus_1_','fy_minus_2_','fy_minus_3_'):
            field=prefix+'diluted_shares'
            if r[field]:continue
            if not all(r.get(prefix+k) for k in ['adsh','period','filed']):
                observations.append(dict(ticker=r['ticker'],field=field,status='MISSING_FILING_IDENTITY'));continue
            cik=str(int(float(r['cik']))).zfill(10);targets.setdefault(cik,[]).append((r,prefix))
    receipts=[]
    for cik,items in sorted(targets.items()):
        url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json';body=None;error=None
        for attempt in range(3):
            time.sleep(0.35 if attempt==0 else 2*(attempt+1))
            try:
                req=urllib.request.Request(url,headers={'User-Agent':f'InvestmentOSDataBridge/1.0 {email}'})
                with urllib.request.urlopen(req,timeout=25) as response:
                    body=response.read();status=response.status
                cf=json.loads(body)
                if int(cf['cik'])!=int(cik):raise ValueError('CIK mismatch')
                break
            except Exception as exc:
                error=type(exc).__name__;body=None
        if body is None:
            observations.extend(dict(ticker=r['ticker'],field=p+'diluted_shares',status='SOURCE_UNAVAILABLE',error=error) for r,p in items);continue
        digest=hashlib.sha256(body).hexdigest();filename=f'raw/CIK{cik}_companyfacts.json.gz';(out/filename).write_bytes(gzip.compress(body,mtime=0))
        receipts.append(dict(cik=cik,url=url,file=filename,sha256=digest,bytes=len(body),http_status=status,retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat()))
        fs=cf.get('facts',{}).get('us-gaap',{}).get(TAG,{}).get('units',{}).get('shares',[])
        for r,p in items:
            f,status=select(fs,r[p+'adsh'],date(r[p+'period']),date(r[p+'filed']))
            ob=dict(ticker=r['ticker'],cik=cik,field=p+'diluted_shares',status=status,source_sha256=digest,unit='shares',concept=TAG)
            if f:ob['fact']=f
            observations.append(ob)
    from collections import Counter
    report=dict(schema='br04_data25_share_source_acquisition_v1',input_sha256=INPUT,issuers_requested=len(targets),issuers_acquired=len(receipts),observations=len(observations),status_counts=dict(Counter(x['status'] for x in observations)),candidate_modified=False,economic_clearance=False,buy_add_allowed=False)
    (out/'sources.json').write_text(json.dumps(dict(receipts=receipts,observations=observations),indent=2)+'\n')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    assert (ROOT/'data/research/br04-data23/RESEARCH_NOT_PROMOTED.csv').read_bytes()==raw
    print('DATA25_REPORT='+json.dumps(report))
    import base64,zlib
    print('DATA25_SOURCES_ZLIB_BASE64='+base64.b64encode(zlib.compress((out/'sources.json').read_bytes())).decode())
if __name__=='__main__':main()
