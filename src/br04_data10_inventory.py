"""Read-only qualification gap inventory; no score, clearance or candidate edits."""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path
from audit_br04_data09 import CANDIDATE_SHA

ECONOMIC_CASES={'FISV','CMCSA','FOX','GM','ADBE','TROW','AMP','NEM','FIX','ANET'}
REQUIRED=['annual_operating_cash_flow','annual_capex','annual_sbc','annual_revenue','annual_diluted_shares','prior_diluted_shares','fy_minus_3_diluted_shares']
LEDGER_SHA='8fde42ccc4941c6ca6d183f6aa984c9eacbc171af36d9eb0d2fc00622fe318af'
PROOFS_SHA='0a143694130f1a2a9d6592a42350023ecf205b9e4d3aafe19d9ab61771b1b676'
FILINGS={'MCD':'0000063908-26-000035','CEG':'0001868275-26-000032','WELL':'0000766704-26-000010'}

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None

def inventory(data,ledger_bytes,proof_bytes):
    for raw,pin,label in [(data,CANDIDATE_SHA,'candidate'),(ledger_bytes,LEDGER_SHA,'ledger'),(proof_bytes,PROOFS_SHA,'proofs')]:
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError(label+' hash mismatch')
    rows=list(csv.DictReader(io.StringIO(data.decode(),newline='')))
    by={r['ticker']:r for r in rows}
    if len(rows)!=len(by) or len(rows)!=504:raise ValueError('universe')
    ledger=list(csv.DictReader(io.StringIO(ledger_bytes.decode(),newline='')))
    differences=[]
    for e in ledger:
        t,k=e['ticker'],e['field']
        if t not in FILINGS:continue
        if by[t]['annual_adsh']!=FILINGS[t]:raise ValueError('prior correction filing changed')
        current=by[t][k];prior=e['after']
        if current==prior:continue
        a,b=number(current),number(prior)
        equivalent=a is not None and b is not None and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
        differences.append(dict(ticker=t,field=k,current=current,prior_documented=prior,rule=e['rule'],same_annual_filing=True,classification='NUMERICALLY_EQUIVALENT_FORMATTING' if equivalent else 'SUBSTANTIVE_REVIEW_REQUIRED',applied=False))
    qualification=[];counts=Counter()
    for r in rows:
        t=r['ticker'];reasons=[]
        if r['total_debt_status']=='CONFLICTING':reasons.append('CONFLICTING_DEBT_MAPPING')
        if r['ios_leverage_indeterminate'].lower()=='true':reasons.append('LEVERAGE_INDETERMINATE')
        if t in ECONOMIC_CASES:reasons.append('ECONOMIC_CASE_REMAINS_BLOCKED')
        if t=='ADBE':reasons.append('ROSCA_UNRESOLVED')
        if t=='IP':reasons.append('ROW_BASIS_REVENUE_MISSING')
        for k in REQUIRED:
            if number(r.get(k)) is None:reasons.append('MISSING_'+k.upper())
        for flag in ['BANK_FUNDING_PERIMETER_UNRESOLVED','INSURANCE_FUNDING_PERIMETER_UNRESOLVED']:
            if flag in r['br04_flags'].split(';'):reasons.append(flag)
        if t=='CVX':reasons.append('STRICT_DEBT_PERIMETER_UNRESOLVED')
        if t=='MCD':reasons.append('DOCUMENTED_SHARE_UNIT_CORRECTION_NOT_REAPPLIED')
        if t in {'CEG','WELL'}:reasons.append('PRIOR_REVENUE_POLICY_REQUIRES_RECONCILIATION')
        counts.update(reasons)
        qualification.append(dict(ticker=t,annual_adsh=r['annual_adsh'],screen_has_open_items=bool(reasons),reasons=reasons,economic_clearance=False,buy_add_allowed=False,system_live=False))
    material=Counter(x['ticker'] for x in differences if x['classification']=='SUBSTANTIVE_REVIEW_REQUIRED')
    summary=dict(schema='br04_data10_readonly_gap_inventory_v1',candidate_sha256=CANDIDATE_SHA,rows=504,open_item_counts=dict(sorted(counts.items())),rows_with_listed_open_items=sum(q['screen_has_open_items'] for q in qualification),rows_without_listed_open_items=sum(not q['screen_has_open_items'] for q in qualification),prior_ledger_string_differences=len(differences),prior_ledger_substantive_differences=sum(material.values()),prior_ledger_substantive_by_ticker=dict(material),prior_ledger_formatting_only=len(differences)-sum(material.values()),economic_cases_present=sorted(ECONOMIC_CASES&by.keys()),economic_cases_absent=sorted(ECONOMIC_CASES-by.keys()),buy_add_blocked_rows=504,candidate_modified=False,source_evidence_scope='Archived RC1 evidence; no fresh SEC authentication',limitations=['Counts overlap; this is a finite mechanical screen, not comprehensive economic clearance.','Absence of a listed reason never authorizes trading.','CEG/WELL total-revenue convention was a development proposal, not an approved production policy.','Historical PH precision evidence cannot be transferred automatically: its annual filing has changed.'],next_action='Revalidate MCD source-unit conversion and recompute per-share CAGR in a separate, explicitly scoped candidate amendment.')
    return summary,qualification,differences

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];out=root/'data/research/br04-data10'
    result=inventory((root/'data/research/br04-data09/RESEARCH_NOT_PROMOTED.csv').read_bytes(),(out/'prior_rc1_ledger.csv').read_bytes(),(out/'prior_rc1_proofs.json').read_bytes())
    for name,value in zip(['open_items.json','qualification.json','prior_amendment_comparison.json'],result):
        (out/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(result[0],indent=2))
