"""Calculate secondary historical leverage only from accession-pinned primary facts.

No ticker-specific code, scoring changes, canonical writes or case clearances.
"""
import argparse, hashlib, json, importlib.util, sys
from decimal import Decimal
from pathlib import Path
from r10f_verify_source_corrections import verify_registry

def load(path):
 spec=importlib.util.spec_from_file_location('frozen_cash_diagnostics',path)
 module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
 return module

def run(registry_path,sources,engine):
 raw=registry_path.read_bytes();registry=json.loads(raw)
 assert hashlib.sha256(engine.read_bytes()).hexdigest()=='1d76a9a260793614edb5964b02eaed71b8b0ce6307fdb257d16773b9adb1ef3a'
 assert all(registry[k] is False for k in ['engine_modified','ranking_recomputed','system_live','normalization_complete'])
 verified=verify_registry(registry,sources)
 values={x['item_id']:Decimal(x['value_usd']) for x in verified['items']}
 assert len(values)==len(registry['items'])
 assert all(x['source_verification']=='PASS' for x in verified['items'])
 fn=load(engine);results=[]
 for case in registry['cases']:
  inputs={k:values[ref] for k,ref in case['input_refs'].items()}
  assert set(inputs)=={'operating_income','da','sbc','gross_debt','cash'}
  assert inputs['da']>=0 and inputs['gross_debt']>=0 and inputs['cash']>=0 and inputs['sbc']>=0
  assert not any(case[k] for k in ['economic_case_closed','buy_add_allowed'])
  assert case['unresolved_material_red_flag'] is True
  ebitda=inputs['operating_income']+inputs['da'];stress=ebitda-inputs['sbc']
  result=fn.leverage_stress_view(gross_debt=float(inputs['gross_debt']),cash=float(inputs['cash']),
                                ebitda=float(ebitda),sbc=float(inputs['sbc']),module=case['module'])
  assert result['status']=='PRESENT' and result['stress_metric_status']=='PRESENT'
  for name,expected in [('gross_debt_to_ebitda',inputs['gross_debt']/ebitda),
                        ('net_debt_to_ebitda',(inputs['gross_debt']-inputs['cash'])/ebitda),
                        ('gross_debt_to_ebitda_after_sbc',inputs['gross_debt']/stress)]:
   assert abs(Decimal(str(result[name]))-expected)<Decimal('0.000000000001')
  results.append({**case,'inputs_usd':{k:str(v) for k,v in inputs.items()},'reported_ebitda_usd':str(ebitda),
                  'reported_ebitda_after_sbc_usd':str(stress),'secondary_view':result,
                  'normalization_complete':False,'normalized_owner_earnings_usd':None,
                  'disposition':'HOLD_UNRESOLVED_NO_BUY_ADD'})
 return {'schema':'r10n_verified_historical_leverage_receipt_v1',
         'registry_sha256':hashlib.sha256(raw).hexdigest(),'status':'SOURCE_AND_ARITHMETIC_PASS_PERIMETER_REVIEWS_OPEN',
         'primary_input_checks_pass':len(verified['items']),'views_calculated':len(results),
         'previously_missing_views_now_calculable':sum(r['prior_r10d_leverage_status']=='MISSING' for r in results),
         'cases':results,'excluded_from_generic_view':registry['excluded_from_generic_view'],
         'engine_modified':False,'ranking_recomputed':False,'system_live':False,'full_case_closures':0,
         'r11_performed':False,'r12_performed':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--sources',type=Path,required=True)
 p.add_argument('--engine',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 result=run(a.registry,a.sources,a.engine);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['status','primary_input_checks_pass','views_calculated','previously_missing_views_now_calculable','full_case_closures']}))
