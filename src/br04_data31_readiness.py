"""Read-only qualification gap inventory; no score, clearance or candidate edits."""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path
CANDIDATE_SHA='dcfce67f685fecb205b2b0028a759bc1e29bed61745b2cd34904d4dba0435a5e'

ECONOMIC_CASES={'FISV','CMCSA','FOX','GM','ADBE','TROW','AMP','NEM','FIX','ANET'}
SBC_SCOPE_REVIEW=set()  # Remaining 17 ticker observations checked against primary award expense disclosures.
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
        if t in SBC_SCOPE_REVIEW:reasons.append('SBC_AWARD_SCOPE_UNVERIFIED')
        if r['total_debt_status']=='CONFLICTING':reasons.append('CONFLICTING_DEBT_MAPPING')
        if r['ios_leverage_indeterminate'].lower()=='true':reasons.append('LEVERAGE_INDETERMINATE')
        if t in ECONOMIC_CASES:reasons.append('ECONOMIC_CASE_REMAINS_BLOCKED')
        if t=='ADBE':reasons.append('ROSCA_UNRESOLVED')
        if t=='IP':reasons.extend(['ROW_BASIS_REVENUE_MISSING','IP_MIXED_CONTINUING_DISCONTINUED_BASIS'])
        if t=='FE':reasons.append('SBC_NET_CAPITALIZATION_POLICY_UNRESOLVED')
        for k in REQUIRED:
            if number(r.get(k)) is None:reasons.append('MISSING_'+k.upper())
        for flag in ['BANK_FUNDING_PERIMETER_UNRESOLVED','INSURANCE_FUNDING_PERIMETER_UNRESOLVED']:
            if flag in r['br04_flags'].split(';'):reasons.append(flag)
        if t=='CVX':reasons.append('STRICT_DEBT_PERIMETER_UNRESOLVED')
        counts.update(reasons)
        qualification.append(dict(ticker=t,annual_adsh=r['annual_adsh'],screen_has_open_items=bool(reasons),reasons=reasons,economic_clearance=False,buy_add_allowed=False,system_live=False))
    material=Counter(x['ticker'] for x in differences if x['classification']=='SUBSTANTIVE_REVIEW_REQUIRED')
    summary=dict(schema='br04_data31_readiness_inventory_v1',candidate_sha256=CANDIDATE_SHA,rows=504,open_item_counts=dict(sorted(counts.items())),rows_with_listed_open_items=sum(q['screen_has_open_items'] for q in qualification),rows_without_listed_open_items=sum(not q['screen_has_open_items'] for q in qualification),prior_ledger_string_differences=len(differences),prior_ledger_substantive_differences=sum(material.values()),prior_ledger_substantive_by_ticker=dict(material),prior_ledger_formatting_only=len(differences)-sum(material.values()),economic_cases_present=sorted(ECONOMIC_CASES&by.keys()),economic_cases_absent=sorted(ECONOMIC_CASES-by.keys()),buy_add_blocked_rows=504,candidate_modified=False,source_evidence_scope='Archived primary evidence, fresh USB/CMCSA filings and DATA25 SEC Companyfacts acquisition; bulk shares have no independent inline-document confirmation',limitations=['Counts overlap; this is a finite mechanical screen, not comprehensive economic clearance.','Absence of a listed reason never authorizes trading.','CEG/WELL total-revenue policy is applied in DATA12 research only, not approved for production.','Historical PH precision evidence cannot be transferred automatically: its annual filing has changed.'],next_action='Resolve remaining economic and source-completeness gaps; do not transfer historical release approvals.')
    return summary,qualification,differences

REGISTRY_SHA='9428786994c547e739f7e4742f9c02ebcb392bc3706c3a81af7d787c0a16ba96'
def main():
    import os,zipfile
    root=Path(__file__).resolve().parents[1];out=root/'data/research/br04-data31';out.mkdir(parents=True,exist_ok=True)
    candidate=root/'data/research/br04-data30/RESEARCH_NOT_PROMOTED.csv';raw=candidate.read_bytes()
    global CANDIDATE_SHA
    from br04_data30_sbc_primary import amend
    import base64,zlib
    proof=(root/'docs/evidence/sbc26_source.json').read_bytes()
    expected,_=amend((root/'data/research/br04-data28/RESEARCH_NOT_PROMOTED.csv').read_bytes(),proof)
    if raw!=expected:raise ValueError('DATA30 reconstruction mismatch')
    CANDIDATE_SHA=hashlib.sha256(expected).hexdigest()
    ev=root/'data/research/br04-data10'
    summary,rows,diffs=inventory(raw,(ev/'prior_rc1_ledger.csv').read_bytes(),(ev/'prior_rc1_proofs.json').read_bytes())
    registry_raw=(root/'docs/evidence/economic_registry_verified.json').read_bytes()
    if hashlib.sha256(registry_raw).hexdigest()!=REGISTRY_SHA:raise ValueError('registry custody mismatch')
    registry=json.loads(registry_raw)
    if len(registry['records'])!=41 or len({x['case_id'] for x in registry['records']})!=10:raise ValueError('registry completeness')
    if not all(x['economic_case_closed'] is False and x['buy_add_allowed'] is False for x in registry['records']):raise ValueError('unexpected clearance')
    runtime=json.loads((candidate.parent/'report.json').read_bytes())
    if runtime['candidate_sha256']!=CANDIDATE_SHA or not runtime['overall_passed']:raise ValueError('runtime mismatch')
    summary.update(archived_economic_records=41,archived_verified_references=64,archived_review_is_current_clearance=False,technical_subissue_resolved='CMCSA liabilities corrected; IP mixed-basis ratios quarantined; economic cases remain open',release_decision='BLOCKED',r11_status='NOT_EXECUTED',r12_status='NOT_EXECUTED',r12_ready=False,system_live=False,buy_add_allowed=False,s6_dispatched=False)
    actions={
        'SBC_AWARD_SCOPE_UNVERIFIED':'Verify total versus award-subset, equity/cash settlement and capitalization against the original primary statement; the BNY counterexample proves exact Companyfacts matching alone is insufficient.',
        'SBC_NET_CAPITALIZATION_POLICY_UNRESOLVED':'FE: reconcile gross 85m versus net-expensed 39m with the SBC/capex policy; do not map a capitalized-cost tag to total SBC by name alone.',
        'IP_MIXED_CONTINUING_DISCONTINUED_BASIS':'Reconstruct a consistent continuing-operations series for revenue, earnings, OCF and capex; current source comparatives differ from original filings. Preserve adapter reinvestment-rate suppression.',
        'ROW_BASIS_REVENUE_MISSING':'IP: establish FY2022 revenue on the same row/business basis; reconcile divestitures and comparative presentation before enabling growth.',
        'STRICT_DEBT_PERIMETER_UNRESOLVED':'CVX: reconcile strict borrowing perimeter separately from leases and guarantees.',
        'BANK_FUNDING_PERIMETER_UNRESOLVED':'Separate deposits/funding from borrowings and record a sector-specific leverage disposition.',
        'INSURANCE_FUNDING_PERIMETER_UNRESOLVED':'Separate insurance liabilities/funding from borrowings before economic leverage qualification.',
        'ECONOMIC_CASE_REMAINS_BLOCKED':'Resolve the linked case-specific residuals with new evidence; archived review is not closure.',
        'ROSCA_UNRESOLVED':'Reconcile Adobe cash-quality and remaining ROSCA exposure with appropriate primary evidence.',
        'LEVERAGE_INDETERMINATE':'Resolve missing/conflicting debt, cash and earnings inputs under the frozen contract; do not infer zero.',
        'CONFLICTING_DEBT_MAPPING':'Reconcile conflicting mappings; retain indeterminate status until resolved.'}
    for row in rows:
        row['disposition']='BLOCKED_EVIDENCE_REQUIRED' if row['reasons'] else 'BLOCKED_INDEPENDENT_REVIEW_REQUIRED'
        row['required_actions']=[actions.get(reason,'Recover '+reason.removeprefix('MISSING_')+' with period, units, accession and dependent metrics verified; otherwise preserve missing.') for reason in row['reasons']]
    files={'open_items.json':summary,'qualification.json':rows,'prior_amendment_comparison.json':diffs,'economic_dispositions.json':registry,'runtime_report.json':runtime,'sbc_primary_scope_review.json':json.loads((root/'docs/evidence/sbc_primary_scope_review.json').read_bytes()),'sbc26_source.json':json.loads(proof),'bulk_share_sources.json':json.loads(zlib.decompress(base64.b64decode((root/'docs/evidence/bulk_share_sources.json.zlib.b64').read_bytes()))),'ip_basis_reconciliation.json':json.loads((root/'docs/evidence/ip_mixed_basis_source.json').read_bytes()),'cmcsa_source_reconciliation.json':json.loads((root/'docs/evidence/cmcsa_liabilities_source.json').read_bytes())}
    for name,value in files.items():(out/name).write_text(json.dumps(value,indent=2)+'\n')
    (out/'RESEARCH_NOT_PROMOTED.csv').write_bytes(raw)
    instructions='''# Review handoff — BLOCKED, not final approval

This package identifies the exact DATA30 candidate and all finite-screen dispositions.
All 504 rows remain BUY/ADD blocked, including rows with no listed mechanical gap.
41 archived flag records across 10 cases remain open. Their 64 references were hash/byte-verified against the archived checkpoint; this is custody verification, not a fresh economic review.
FE requires gross-versus-net capitalization policy resolution. IP requires comparable row-basis revenue. Missing data must not become zero. Economic qualification and R11 have not passed; R12 has not been executed.

Completion sequence:
1. Resolve or explicitly reject each material source/economic issue with evidence. A BLOCKED disposition documents a decision but does not satisfy clearance.
2. Run R11 on the exact final candidate after changes, with all financial dependencies reconciled.
3. Only after R11 eligibility, run R12 in a separate blind context with no development archive or previous conclusions. This package is a development handoff, NOT that blind context.
4. Tie signed review outcomes to exact input/engine hashes; any material change invalidates the relevant approval.
5. Prepare bootstrap, IPS, ledgers and operational dry-run only after the review gates. No LIVE or S6 action is authorized by this package.

DATA23 suppresses IP revenue growth, net/FCF margins and its research adapter reinvestment_rate because their inputs cross accounting bases. Raw values are preserved. Consumers must honor the basis flag; generic recomputation would reintroduce invalid ratios.

DATA26 adds bulk shares selected from exact original SEC Companyfacts accessions/annual periods/units, rejecting later conflicting values. This is source recovery, not independent inline verification or economic qualification. Source receipt files were preserved in DATA25 acquisition run 40847031311.

DATA28 recovers 17 SBC observations checked against primary expense disclosures. GE after-tax and AES award-subset values are excluded; see sbc_primary_scope_review.json. It also recovers and two historical INTU values from the same receipt-verified Companyfacts corpus; source scope is explicit and does not constitute economic clearance. Broad productive-asset capex facts remain excluded pending primary reconciliation.

DATA30 adds 33 primary-confirmed SBC expenses and recomputes dependent ratios/status; 7 unresolved issuer cases remain excluded.

Source code and pinned evidence are in the accompanying Git commit. Re-run the research workflow to reconstruct generated files. No production data is changed.
'''
    (out/'REVIEW_HANDOFF.md').write_text(instructions)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name not in ['manifest.json','research-review-handoff.zip']}
    (out/'manifest.json').write_text(json.dumps(dict(files=manifest,candidate_sha256=CANDIDATE_SHA,commit=os.environ.get('GITHUB_SHA'),release_decision='BLOCKED'),indent=2)+'\n')
    with zipfile.ZipFile(out/'research-review-handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in sorted(list(manifest)+['manifest.json']):z.write(out/name,name)
    with zipfile.ZipFile(out/'research-review-handoff.zip') as z:
        if z.testzip() is not None:raise ValueError('archive integrity')
        for name,h in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=h:raise ValueError('archive member mismatch')
    if candidate.read_bytes()!=raw:raise ValueError('candidate mutated')
    print('DATA31_REPORT='+json.dumps(summary))
if __name__=='__main__':main()
