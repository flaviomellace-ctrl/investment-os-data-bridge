import csv,json,hashlib
from pathlib import Path
from collections import Counter
import argparse,importlib.util,sys
parser=argparse.ArgumentParser(description='Aggregate frozen-engine compatibility diagnostic; not R11/R12.')
for arg in ['candidate','v41','v42','adapter','out']:parser.add_argument('--'+arg,required=True)
args=parser.parse_args()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
preflight=load('diagnostic_adapter',args.adapter)
v41=load('diagnostic_v41',args.v41)
v42=load('diagnostic_v42',args.v42)
raw=Path(args.candidate).read_bytes();assert hashlib.sha256(raw).hexdigest()=='5a6802101110ee3a90ef1919a04e4414d03638f9d165852cce37bcd5911666a8'
assert hashlib.md5(Path(args.v41).read_bytes()).hexdigest()=='68f626974592915d6c2a8e6583d6c77b'
assert hashlib.sha256(Path(args.v42).read_bytes()).hexdigest()=='cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e'
gates=[Counter(),Counter()];transitions=Counter();lost=Counter();bqs_differences=0;adapter_overwrites=Counter()
for r in csv.DictReader(raw.decode().splitlines()):
 results=[]
 for i,e in enumerate([v41,v42]):
  c=preflight.derive(r,e)
  if r['ticker']=='IP':
   assert c['fcf_margin'] is None and c['net_margin'] is None;c['reinvestment_rate']=None
  if i==1:
   for k in ['combined_ratio','ffo_margin','occupancy','ebitda_on_volume','fcf_on_volume','take_rate','affo']:
    if r.get(k) and c.get(k) is None:adapter_overwrites[k]+=1
  b,cov,detail,flags=e.bqs(c);v,d=e.ios(c,b,cov);gate='CALCULABLE' if v is not None else d.get('gate','UNSPECIFIED');gates[i][gate]+=1;results.append((v,b,gate))
 transitions[str(results[0][0] is not None)+' -> '+str(results[1][0] is not None)]+=1
 if results[0][0] is not None and results[1][0] is None:lost[results[1][2]]+=1
 bqs_differences+=results[0][1]!=results[1][1]
report={'candidate_sha256':hashlib.sha256(raw).hexdigest(),'rows':504,'v41_gate_counts':dict(gates[0]),'v42_gate_counts':dict(gates[1]),'computability_transitions':dict(transitions),'lost_computability_reasons':dict(lost),'bqs_differences':bqs_differences,'nonempty_sector_fields_suppressed_by_adapter':dict(adapter_overwrites),'scope':'Same DATA09 SIC adapter and IP basis suppression for both frozen engines; no documentary BR09 rerouting or full V4.2 overlays. Aggregate diagnostic, not validation.','candidate_modified':False,'r11_status':'NOT_EXECUTED','r12_status':'NOT_EXECUTED','system_live':False}
Path(args.out).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
