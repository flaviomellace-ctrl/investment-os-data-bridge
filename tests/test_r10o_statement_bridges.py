"""Negative controls against incorrect cash signs and unsupported clearance."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from r10o_verify_statement_bridges import verify

if __name__=='__main__':
    registry=json.loads(Path(sys.argv[1]).read_text())
    sources=Path(sys.argv[2])
    mutations=[
        ('incorrect_cashflow_sign',lambda r:r['equations'][0]['terms'][5].update(coefficient=1)),
        ('duplicate_fact_reference',lambda r:r['items'].append(copy.deepcopy(r['items'][0]))),
        ('invented_capex_ratio',lambda r:r['capex_sensitivity'].update(difference_ratio='0')),
        ('conditional_cash_use_changed',lambda r:r['conditional_commitments'][0].update(amount_usd='0')),
        ('unsupported_normalization',lambda r:r.update(normalization_complete=True)),
        ('case_clearance_without_evidence',lambda r:r.update(economic_case_closed=True)),
        ('narrative_claim_not_in_source',lambda r:r['narratives'][0].update(excerpt='Invented cash tax benefit in the frozen year')),
    ]
    for name,mutate in mutations:
        candidate=copy.deepcopy(registry);mutate(candidate)
        try:verify(candidate,sources)
        except ValueError as e:print('PASS',name,str(e))
        else:raise AssertionError('FAILED TO REJECT: '+name)
    print('PASS',len(mutations),'negative controls')
