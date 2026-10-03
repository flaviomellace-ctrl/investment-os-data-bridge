"""Verify accession-pinned statement equations and excerpts; never changes engine inputs."""
import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from lxml import html
from r10f_verify_source_corrections import verify_registry

def verify(registry, sources):
    primary=verify_registry(registry,sources)
    facts={r['item_id']:Decimal(r['value_usd']) for r in primary['items']}
    if len(facts)!=len(primary['items']): raise ValueError('DUPLICATE_ITEM_ID')
    equations=[]
    for spec in registry['equations']:
        value=sum((facts[x['item_id']]*Decimal(str(x['coefficient'])) for x in spec['terms']),Decimal(0))
        target=facts[spec['target_item_id']] if 'target_item_id' in spec else Decimal(spec['expected_result_usd'])
        if value!=target: raise ValueError('STATEMENT_BRIDGE_MISMATCH: '+spec['equation_id'])
        equations.append({'equation_id':spec['equation_id'],'value_usd':str(value),'difference_usd':str(value-target),'status':'PASS'})
    narratives=[]
    cache={}
    for spec in registry['narratives']:
        name=spec['source_file']
        if Path(name).name!=name: raise ValueError('UNSAFE_SOURCE_PATH')
        content=(sources/name).read_bytes()
        if hashlib.sha256(content).hexdigest()!=spec['source_sha256']: raise ValueError('NARRATIVE_SOURCE_CHANGED')
        if name not in cache:
            cache[name]=re.sub(r'\s+',' ',' '.join(html.fromstring(content).itertext())).strip()
        occurrences=cache[name].count(spec['excerpt'])
        if occurrences!=spec['expected_occurrences']: raise ValueError('NARRATIVE_CHANGED: '+spec['narrative_id'])
        narratives.append({'narrative_id':spec['narrative_id'],'occurrences':occurrences,'status':'PASS'})
    sensitivity=registry['capex_sensitivity']
    mixed=Decimal(sensitivity['mixed_line_usd'])
    reported=Decimal(sensitivity['reported_oe_usd'])
    endpoint=Decimal(sensitivity['full_mixed_line_deduction_sensitivity_usd'])
    equations_by_id={r['equation_id']:Decimal(r['value_usd']) for r in equations}
    if (mixed!=facts[sensitivity['source_item_id']] or reported!=equations_by_id['REPORTED_OE_UNCHANGED']
        or endpoint!=equations_by_id['CAPEX_MIXED_LINE_FULL_DEDUCTION_SENSITIVITY_ONLY']
        or reported-endpoint!=mixed or abs(mixed/reported-Decimal(sensitivity['difference_ratio']))>Decimal('1e-17')
        or sensitivity['is_normalized_owner_earnings'] or sensitivity['is_total_cash_quality_bound']):
        raise ValueError('INVALID_CAPEX_SENSITIVITY_SCOPE_OR_ARITHMETIC')
    for commitment in registry['conditional_commitments']:
        if 'source_item_id' in commitment and Decimal(commitment['amount_usd'])!=facts[commitment['source_item_id']]:
            raise ValueError('COMMITMENT_AMOUNT_CHANGED')
    if registry['engine_modified'] or registry['ranking_recomputed'] or registry['system_live'] or registry['economic_case_closed']:
        raise ValueError('UNSUPPORTED_CLEARANCE')
    if registry['normalized_owner_earnings_usd'] is not None or registry['normalization_complete'] or registry['buy_add_allowed']:
        raise ValueError('UNSUPPORTED_NORMALIZATION_OR_ACTION')
    return {'schema':'r10o_statement_bridge_verification_v1','source_inputs_verified':len(facts),
            'equations':equations,'narratives':narratives,'equations_passed':len(equations),'narratives_passed':len(narratives),
            'status':'PRIMARY_STATEMENT_AND_DOCUMENTARY_DISPOSITIONS_PASS_FULL_CASE_OPEN',
            'subflag_dispositions':registry['subflag_dispositions'],'conditional_commitments':registry['conditional_commitments'],
            'capex_sensitivity':registry['capex_sensitivity'],'economic_case_closed':False,
            'normalization_complete':False,'normalized_owner_earnings_usd':None,'buy_add_allowed':False,
            'engine_modified':False,'ranking_recomputed':False,'r11_performed':False,'r12_performed':False,'system_live':False}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--registry',type=Path,required=True)
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists(): raise SystemExit('Refusing to overwrite receipt')
    result=verify(json.loads(a.registry.read_text()),a.sources)
    result['registry_sha256']=hashlib.sha256(a.registry.read_bytes()).hexdigest()
    result['verifier_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('subflag_dispositions','conditional_commitments','capex_sensitivity')},indent=2))
