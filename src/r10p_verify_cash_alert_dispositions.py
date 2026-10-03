"""Verify the provenance and exact coverage of original cash-alert dispositions."""
import argparse,csv,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from lxml import html
from r10f_verify_source_corrections import verify_registry

def verify(reg,sources,overlay):
    if hashlib.sha256(overlay.read_bytes()).hexdigest()!=reg['original_overlay_sha256']:
        raise ValueError('ORIGINAL_OVERLAY_CHANGED')
    with overlay.open(newline='') as f:rows=list(csv.DictReader(f))
    expected={(r['ticker'],flag) for r in rows for flag in r['cash_quality_flags'].split('|') if flag}
    actual=[(r['ticker'],r['original_flag']) for r in reg['dispositions']]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:
        raise ValueError('ORIGINAL_ALERT_COVERAGE_MISMATCH')
    primary=verify_registry(reg,sources)
    values={r['item_id']:Decimal(r['value_usd']) for r in primary['items']}
    equations=[]
    for equation in reg['equations']:
        result=sum((values[t['item_id']]*Decimal(str(t['coefficient'])) for t in equation['terms']),Decimal(0))
        if result!=Decimal(equation['expected_result_usd']):raise ValueError('NONCASH_BRIDGE_MISMATCH')
        equations.append({'equation_id':equation['equation_id'],'result_usd':str(result),'status':'PASS'})
    narratives=[]
    for n in reg['narratives']:
        if Path(n['source_file']).name!=n['source_file']:raise ValueError('UNSAFE_SOURCE_PATH')
        b=(sources/n['source_file']).read_bytes()
        if hashlib.sha256(b).hexdigest()!=n['source_sha256']:raise ValueError('SOURCE_CHANGED')
        text=re.sub(r'\s+',' ',' '.join(html.fromstring(b).itertext())).strip()
        count=text.count(n['excerpt'])
        if count!=n['expected_occurrences']:raise ValueError('EXCERPT_CHANGED')
        narratives.append({'narrative_id':n['narrative_id'],'status':'PASS','occurrences':count})
    ids={r['item_id'] for r in primary['items']}
    nids={r['narrative_id'] for r in narratives}
    for d in reg['dispositions']:
        if not set(d['numeric_refs'])<=ids or not set(d['narrative_refs'])<=nids:
            raise ValueError('UNRESOLVED_EVIDENCE_REFERENCE')
        if not d['numeric_refs'] and not d['narrative_refs']:raise ValueError('NO_DISPOSITION_EVIDENCE')
        if d['economic_case_closed'] or d['buy_add_allowed'] or d['normalization_complete'] or d['normalized_owner_earnings_usd'] is not None:
            raise ValueError('UNSUPPORTED_WHOLE_CASE_CLEARANCE')
    if reg['engine_modified'] or reg['ranking_recomputed'] or reg['system_live'] or reg['r11_performed'] or reg['r12_performed']:
        raise ValueError('UNSUPPORTED_ENGINE_OR_VALIDATION_STATE')
    handled=sum(d['original_alert_handled'] for d in reg['dispositions'])
    return {'schema':'r10p_original_cash_alert_receipt_v1','original_alerts':len(expected),
            'original_alerts_handled':handled,'original_alerts_still_open':len(expected)-handled,
            'source_inputs_verified':len(primary['items']),'narrative_checks_passed':len(narratives),
            'equations':equations,'equations_passed':len(equations),
            'narratives':narratives,'dispositions':reg['dispositions'],
            'economic_annotations_not_semantically_certified':True,'independent_human_review_performed':False,
            'aggregate_cash_reviews_still_open':True,'economic_cases_closed':0,'economic_cases_open':10,
            'engine_modified':False,'ranking_recomputed':False,'r11_performed':False,'r12_performed':False,'system_live':False}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--registry',type=Path,required=True);p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--overlay',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise SystemExit('Refusing to overwrite receipt')
    r=verify(json.loads(a.registry.read_text()),a.sources,a.overlay)
    r['registry_sha256']=hashlib.sha256(a.registry.read_bytes()).hexdigest()
    r['verifier_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('dispositions','narratives')},indent=2))
