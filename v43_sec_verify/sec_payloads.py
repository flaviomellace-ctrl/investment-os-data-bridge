#!/usr/bin/env python3
"""V4.3 development 0.6 - SEC payload fetch (GitHub workflow) and offline checks.

fetch   NETWORK. Downloads every (cik, taxonomy, concept) of the fetch list from
        data.sec.gov/api/xbrl/companyconcept, stores the raw bytes and writes
        PAYLOAD_RECEIPT.json (SHA-256 and size of every payload, origin
        SEC_HTTPS). HTTP 404 is recorded as ABSENT_AT_SEC_HTTP_404; any other
        failure aborts. A 404 is confirmed by a second request before it is
        recorded. Declared User-Agent, below 3 requests per second.
        Writes only into --out. Never writes into a repository tree.
check   OFFLINE. Compares the model-extracted evidence ledger and the 244 direct
        provenance cells of the accepted composition with a payload directory.
        An accession that is not in the SEC payload cannot be CONFIRMED.

Exit codes (both commands): 0 = done and, for check, every row CONFIRMED;
1 = check completed and some rows are not confirmed (a RESULT, not a failure);
2 = technical error (payloads refused, bad input, network, crash). A caller
must treat 2 as a failed run and must never read it as "rows not confirmed".
"""
import os,sys
sys.dont_write_bytecode=True
try:os.remove(__cached__);os.rmdir(os.path.dirname(__cached__))
except (NameError,TypeError,OSError):pass
import argparse,csv,gzip,hashlib,json,time,urllib.error,urllib.request
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import facts as F
DIRECT='EXACT_PERIOD_ANNUAL_FORM_ANNUAL_DURATION_PREREGISTERED_CONCEPT'
class Technical(Exception):pass
def read(p):
    with Path(p).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def fetch(a):
    email=os.getenv('SEC_CONTACT_EMAIL','').strip()
    if '@' not in email:raise Technical('SEC_CONTACT_EMAIL required (declared User-Agent, SEC fair access)')
    if a.out.exists():raise Technical('output directory already exists')
    keys=sorted({(x['cik'],x['taxonomy'],x['concept']) for x in read(a.list)})
    a.out.mkdir(parents=True);(a.out/'raw').mkdir();entries=[]
    for cik,tax,concept in keys:
        url=f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{tax}/{concept}.json'
        req=urllib.request.Request(url,headers={'User-Agent':f'InvestmentOSDataBridge/1.0 {email}','Accept-Encoding':'gzip'})
        e={'cik':cik,'taxonomy':tax,'concept':concept,'url':url,'retrieved_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        n404=0
        for attempt in range(3):
            time.sleep(0.4+attempt*2)
            try:
                with urllib.request.urlopen(req,timeout=60) as r:
                    raw=r.read();body=gzip.decompress(raw) if r.headers.get('Content-Encoding','')=='gzip' else raw
                json.loads(body);(a.out/'raw'/F.key_name(cik,tax,concept)).write_bytes(body)
                e.update(status='FETCHED',sha256=hashlib.sha256(body).hexdigest(),bytes=len(body));break
            except urllib.error.HTTPError as h:
                if h.code==404:
                    n404+=1
                    if n404>=2:e.update(status='ABSENT_AT_SEC_HTTP_404',http_404_responses=n404);break
                err=repr(h)
            except Exception as x:err=repr(x)
        else:raise Technical(f'FETCH_FAILED {url}: {err}')
        entries.append(e)
    rec={'schema':'v43_sec_payload_receipt_v1','origin':'SEC_HTTPS','fetch_list_sha256':hashlib.sha256(a.list.read_bytes()).hexdigest(),
         'github_run_id':os.getenv('GITHUB_RUN_ID',''),'github_sha':os.getenv('GITHUB_SHA',''),'github_repository':os.getenv('GITHUB_REPOSITORY',''),
         'fetched':sum(x['status']=='FETCHED' for x in entries),'absent':sum(x['status']!='FETCHED' for x in entries),'payloads':entries}
    b=(json.dumps(rec,indent=2)+'\n').encode();(a.out/'PAYLOAD_RECEIPT.json').write_bytes(b)
    print(json.dumps({'fetched':rec['fetched'],'absent':rec['absent'],'absent_keys':['/'.join((x['cik'],x['taxonomy'],x['concept'])) for x in entries if x['status']!='FETCHED'],'PAYLOAD_RECEIPT_SHA256':hashlib.sha256(b).hexdigest()}))
def check(a):
    if a.out.exists():raise Technical('output file already exists')
    if not (a.ledger or a.provenance):raise Technical('nothing to check: give --ledger and/or --provenance')
    try:payloads,rec=F.load_payloads(a.payloads,a.receipt_sha256,a.origin)
    except F.Blocked as e:raise Technical('PAYLOADS_BLOCKED: '+str(e))
    want=[]
    if a.ledger:want+=[dict(set='LEDGER',ticker=x['ticker'],field='',cik=x['cik'],taxonomy='us-gaap',concept=x['concept'],unit=x['unit'],start=x['start'],end=x['end'],val=x['val'],accn=x['accn'],form=x['form'],filed=x['filed']) for x in read(a.ledger)]
    if a.provenance:want+=[dict(set='PROVENANCE',ticker=x['ticker'],field=x['field'],cik=x['cik'],taxonomy=x['taxonomy'],concept=x['concept'],unit=x['unit'],start=x['start'],end=x['end'],val=x['value'],accn=x['accession'],form=x['form'],filed=x['filed']) for x in read(a.provenance) if x['rule']==DIRECT]
    out=[]
    for x in want:
        k=(x['cik'],x['taxonomy'],x['concept'])
        if k not in payloads:status='PAYLOAD_NOT_IN_RECEIPT'
        elif payloads[k] is None:status='CONCEPT_ABSENT_AT_SEC'
        else:
            fs=payloads[k].get('units',{}).get(x['unit'],[])
            def m(f,strict):
                try:ok=float(f.get('val'))==float(x['val'])
                except (TypeError,ValueError):ok=False
                return ok and f.get('end')==x['end'] and f.get('form')==x['form'] and (not x['start'] or f.get('start')==x['start']) and (not strict or (f.get('accn')==x['accn'] and f.get('filed')==x['filed']))
            status='CONFIRMED' if any(m(f,True) for f in fs) else 'VALUE_AND_PERIOD_FOUND_BUT_ACCESSION_OR_FILED_DIFFERS' if any(m(f,False) for f in fs) else 'NOT_FOUND'
        out.append(dict(x,status=status))
    with a.out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    summ={s:{'rows':sum(x['set']==s for x in out),'confirmed':sum(x['set']==s and x['status']=='CONFIRMED' for x in out)} for s in sorted({x['set'] for x in out})}
    bad=sum(x['status']!='CONFIRMED' for x in out);print(json.dumps({'origin':rec['origin'],'summary':summ,'not_confirmed':bad,'not_confirmed_by_status':dict(sorted(Counter(x['status'] for x in out if x['status']!='CONFIRMED').items())),'VERIFICATION_CSV_SHA256':hashlib.sha256(a.out.read_bytes()).hexdigest(),'technical_error':False}));return 1 if bad else 0
def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    f=sub.add_parser('fetch');f.add_argument('--list',type=Path,required=True);f.add_argument('--out',type=Path,required=True)
    c=sub.add_parser('check');c.add_argument('--payloads',type=Path,required=True);c.add_argument('--receipt-sha256',required=True);c.add_argument('--origin',default='SEC_HTTPS');c.add_argument('--ledger',type=Path);c.add_argument('--provenance',type=Path);c.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    try:code=(fetch if a.cmd=='fetch' else check)(a) or 0
    except Technical as e:print('TECHNICAL_ERROR: '+str(e),file=sys.stderr);code=2
    except Exception as e:print('TECHNICAL_ERROR: UNEXPECTED_'+type(e).__name__+': '+str(e)[:200],file=sys.stderr);code=2
    sys.exit(code)
if __name__=='__main__':main()
