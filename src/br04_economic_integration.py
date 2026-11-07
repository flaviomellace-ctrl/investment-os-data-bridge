"""Bind economic cases to the exact research candidate; never release it."""
import csv,hashlib,importlib.util,json,sys
from pathlib import Path
import br04_economic_gate as gate
ROOT=Path(__file__).resolve().parents[1]
def main():
 raw=(ROOT/'data/research/br04-data30/RESEARCH_NOT_PROMOTED.csv').read_bytes()
 sha=hashlib.sha256(raw).hexdigest()
 if sha!=gate.CANDIDATE_SHA:raise ValueError('candidate hash mismatch')
 records=gate.load_registry((ROOT/'docs/evidence/economic_registry_verified.json').read_bytes())
 p=ROOT/'src/investment_os/v4_2/v4_scoring.py'
 if hashlib.sha256(p.read_bytes()).hexdigest()!='cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e':raise ValueError('engine hash mismatch')
 spec=importlib.util.spec_from_file_location('bound_v42',p);e=importlib.util.module_from_spec(spec);sys.modules[spec.name]=e;spec.loader.exec_module(e)
 rows=list(csv.DictReader(raw.decode().splitlines()))
 if len(rows)!=504 or len({r['ticker'] for r in rows})!=504:raise ValueError('universe mismatch')
 results=[gate.evaluate(r,records,e,candidate_sha=sha) for r in rows]
 if sum(len(r['economic_flag_ids']) for r in results)!=41:raise ValueError('lost economic case binding')
 if any(r['buy_add_allowed'] for r in results):raise ValueError('unexpected release')
 out=ROOT/'data/research/economic-gate';out.mkdir(parents=True,exist_ok=True)
 report={'candidate_sha256':sha,'rows':len(rows),'bound_economic_flags':41,'bound_cases':10,'buy_add_blocked_rows':504,'economic_clearance':False,'system_live':False,'r11_status':'NOT_EXECUTED','r12_status':'NOT_EXECUTED','scope':'Research integration only; unresolved flags are enforced, not resolved.'}
 (out/'rows.json').write_text(json.dumps(results,indent=2)+'\n');(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('ECONOMIC_GATE_REPORT='+json.dumps(report))
if __name__=='__main__':main()
