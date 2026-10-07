#!/usr/bin/env python3
"""V4.3 development 0.6 - verified SEC facts and period matching.

Facts come ONLY from raw SEC companyconcept payloads whose SHA-256 is listed in
a payload receipt. Nothing here reads the model-extracted evidence ledger.

Period matching (contracts R13/R14/R20, calendar clause):
  * annual form, annual duration [DUR_MIN, DUR_MAX] days;
  * point in time: fact filed on or before the filing date of the row;
  * fiscal year proven STRUCTURALLY, never from a label: the row's own fiscal
    year must be reported in the row's own filing, and every earlier year is
    reached by walking back contiguous annual periods (start = previous end
    + 1 day), one unique period per step;
  * calendar tolerance: the period found must end within TOL_DAYS of the
    normalized period stored in the row. Tolerance alone never selects a fact.
"""
import os,sys
sys.dont_write_bytecode=True
# If this module was IMPORTED by an interpreter started without -B, Python wrote
# its bytecode before running this line: remove that one file again.
try:os.remove(__cached__);os.rmdir(os.path.dirname(__cached__))
except (NameError,TypeError,OSError):pass
import hashlib,json,math,re
from datetime import date,timedelta
from pathlib import Path

ANNUAL_FORMS=frozenset({'10-K','20-F','40-F'})
TOL_DAYS=7
DUR_MIN,DUR_MAX=350,378
BASIS_TOL=0.005
ISO=re.compile(r'\d{4}-\d{2}-\d{2}')
ACCN=re.compile(r'\d{10}-\d{2}-\d{6}')
ORIGINS=('SEC_HTTPS','PREVIEW_MODEL_EXTRACTED_LEDGER')

class Blocked(ValueError):pass
class NoMatch(Exception):
    def __init__(self,reason):super().__init__(reason);self.reason=reason
def require(c,msg):
    if not c:raise Blocked(msg)
def iso(s):
    if not (isinstance(s,str) and ISO.fullmatch(s)):raise ValueError('invalid ISO date')
    return date.fromisoformat(s)
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def key_name(cik,tax,concept):return f'CIK{cik}_{tax}_{concept}.json'

def _json(b,what):
    try:return json.loads(b)
    except (ValueError,UnicodeDecodeError):raise Blocked(what+' is not valid JSON')
def _well_formed(j):
    """A companyconcept payload: object with units = {unit: [fact objects]}."""
    if not isinstance(j,dict):return False
    u=j.get('units',{})
    return isinstance(u,dict) and all(isinstance(k,str) and isinstance(v,list) and all(isinstance(f,dict) for f in v) for k,v in u.items())

def load_payloads(directory,receipt_sha256,origin):
    """Return {(cik,taxonomy,concept): payload|None(absent at SEC)} and the receipt.

    Every raw file is re-hashed. The receipt hash is the pin a human copies from
    the workflow run; a directory whose receipt differs is refused. Neither the
    directory, nor raw/, nor any file may be a symbolic link. `origin` is only a
    declaration inside the receipt: it routes PREVIEW fixtures away from
    VERIFIED mode (together with their marker) but certifies nothing.
    """
    d=Path(directory);rp=d/'PAYLOAD_RECEIPT.json';raw=d/'raw'
    require(origin in ORIGINS,'unknown payload origin requested')
    require(not d.is_symlink() and d.is_dir(),'payload directory missing or symlink')
    require(not raw.is_symlink(),'payload raw directory is a symlink')
    require(rp.is_file() and not rp.is_symlink(),'payload receipt missing or symlink')
    rb=rp.read_bytes();require(sha_bytes(rb)==receipt_sha256,'payload receipt hash does not match the pinned value')
    rec=_json(rb,'payload receipt');require(isinstance(rec,dict) and rec.get('schema')=='v43_sec_payload_receipt_v1','payload receipt schema mismatch')
    require(rec.get('origin')==origin,'payload origin does not match the requested mode')
    require(isinstance(rec.get('payloads'),list) and all(isinstance(e,dict) and all(isinstance(e.get(k),str) for k in ('cik','taxonomy','concept','status')) for e in rec['payloads']),'payload receipt entries malformed')
    out={};listed=set()
    for e in rec['payloads']:
        k=(e['cik'],e['taxonomy'],e['concept']);require(k not in out,'duplicate payload entry')
        require(re.fullmatch(r'\d{10}',e['cik']) and re.fullmatch(r'[A-Za-z0-9-]+',e['taxonomy']) and re.fullmatch(r'[A-Za-z0-9]+',e['concept']),'unsafe payload key')
        if e['status']=='ABSENT_AT_SEC_HTTP_404':out[k]=None;continue
        require(e['status']=='FETCHED' and isinstance(e.get('sha256'),str) and isinstance(e.get('bytes'),int),'payload entry is neither fetched nor absent')
        p=raw/key_name(*k);listed.add(p.name)
        require(p.is_file() and not p.is_symlink(),'payload file missing or symlink: '+p.name)
        b=p.read_bytes();require(sha_bytes(b)==e['sha256'] and len(b)==e['bytes'],'payload hash mismatch: '+p.name)
        j=_json(b,'payload '+p.name);require(_well_formed(j),'payload structure malformed: '+p.name)
        require(str(j.get('cik','')).isdigit() and int(j['cik'])==int(e['cik']) and j.get('tag')==e['concept'] and j.get('taxonomy')==e['taxonomy'],'payload identity mismatch: '+p.name)
        marker=j.get('PREVIEW_NOT_SEC_BYTES') is True
        require(marker==(origin=='PREVIEW_MODEL_EXTRACTED_LEDGER'),'preview marker inconsistent with payload origin: '+p.name)
        out[k]=j
    if raw.exists():require(raw.is_dir() and {x.name for x in raw.iterdir()}==listed,'unlisted or missing file in payload directory')
    else:require(not listed,'payload raw directory missing')
    return out,rec

def annual_facts(payload,unit,row_filed):
    """Annual-form, annual-duration facts available on or before row_filed."""
    out=[];D=iso(row_filed)
    for f in (payload or {}).get('units',{}).get(unit,[]):
        try:
            if not isinstance(f,dict):continue
            if f.get('form') not in ANNUAL_FORMS:continue
            if not ('start' in f and ACCN.fullmatch(str(f.get('accn','')))):continue
            s,e,fd=iso(f['start']),iso(f['end']),iso(f['filed']);v=f['val']
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):continue
        except (ValueError,KeyError,TypeError):continue
        if fd>D or fd<e:continue
        if not DUR_MIN<=(e-s).days<=DUR_MAX:continue
        out.append({'start':s,'end':e,'val':v,'accn':f['accn'],'form':f['form'],'filed':fd})
    return out

def period_values(facts,period):
    return [f for f in facts if (f['start'],f['end'])==period]

def fiscal_chain(facts,row_accn,row_period,steps):
    """Periods [fy0, fy-1, ... fy-steps], fiscal year proven by contiguity."""
    target=iso(row_period)
    own={(f['start'],f['end']) for f in facts if f['accn']==row_accn and abs((f['end']-target).days)<=TOL_DAYS}
    if not own:raise NoMatch('FISCAL_YEAR_0_NOT_REPORTED_IN_ROW_FILING')
    if len(own)!=1:raise NoMatch('FISCAL_YEAR_0_AMBIGUOUS_IN_ROW_FILING')
    chain=[next(iter(own))];allp={(f['start'],f['end']) for f in facts}
    for _ in range(steps):
        prev_end=chain[-1][0]-timedelta(days=1);nxt={p for p in allp if p[1]==prev_end}
        if not nxt:raise NoMatch('FISCAL_YEAR_CHAIN_BROKEN_NO_CONTIGUOUS_ANNUAL_PERIOD')
        if len(nxt)!=1:raise NoMatch('FISCAL_YEAR_CHAIN_AMBIGUOUS')
        chain.append(next(iter(nxt)))
    return chain

def check_tolerance(period,normalized):
    if abs((period[1]-iso(normalized)).days)>TOL_DAYS:raise NoMatch('PERIOD_END_OUTSIDE_CALENDAR_TOLERANCE')

def distinct(vals):return sorted({float(v) for v in vals})
def same(a,b):return a==b or (b!=0 and abs(a/b-1)<=BASIS_TOL)

def row_basis_value(facts,row_accn,period):
    """Value of `period` on the reporting basis of the row's own filing.

    Returns (value, source_fact, overlap_periods). Direct facts only:
      1. the row's own filing reports the period -> that fact;
      2. otherwise a filing G (already filed, by construction of `facts`) that
         reports the period AND agrees with the row filing, within BASIS_TOL, on
         EVERY annual period both of them report, with at least one such period.
    A value that would require multiplying by a restatement ratio is never
    produced: NoMatch('NO_DIRECT_FACT_ON_ROW_BASIS').
    """
    by_accn={}
    for f in facts:by_accn.setdefault(f['accn'],{}).setdefault((f['start'],f['end']),set()).add(float(f['val']))
    F=by_accn.get(row_accn,{})
    # a row filing that reports two values for one annual period defines no basis at all
    if any(len(v)!=1 for v in F.values()):raise NoMatch('ROW_FILING_REPORTS_CONFLICTING_VALUES')
    pv=period_values(facts,period)
    if not pv:raise NoMatch('NO_FACT_FOR_PERIOD')
    own=[f for f in pv if f['accn']==row_accn]
    if own:return own[0]['val'],own[0],0
    good=[]
    for f in pv:
        G=by_accn[f['accn']];overlap=[p for p in G if p in F]
        if not overlap or len(G[period])!=1:continue
        if all(len(G[p])==1 and len(F[p])==1 and same(next(iter(G[p])),next(iter(F[p]))) for p in overlap):good.append((f,len(overlap)))
    if not good:raise NoMatch('NO_DIRECT_FACT_ON_ROW_BASIS')
    vals=distinct(f['val'] for f,_ in good)
    if not all(same(v,vals[0]) for v in vals):raise NoMatch('SAME_BASIS_FILINGS_DISAGREE')
    f,n=max(good,key=lambda x:(x[0]['filed'],x[0]['accn']));return f['val'],f,n
