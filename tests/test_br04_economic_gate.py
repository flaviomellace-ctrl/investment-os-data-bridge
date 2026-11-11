import csv,hashlib,itertools,json,unittest
from pathlib import Path
import sys,importlib.util
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import br04_economic_gate as gate
engine_path=ROOT/'src/investment_os/v4_2/v4_scoring.py'
assert hashlib.sha256(engine_path.read_bytes()).hexdigest()=='cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e'
spec=importlib.util.spec_from_file_location('frozen_v42_gate',engine_path)
v42=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v42;spec.loader.exec_module(v42)
class GateTests(unittest.TestCase):
 def test_frozen_gate_truth_table(self):
  for live,done,red,conflict in itertools.product([False,True],repeat=4):
   allowed,_=v42.can_emit_buy(live,done,red,conflict)
   self.assertEqual(allowed,live and done and not red and not conflict)
 def test_each_open_case_blocks_even_if_live_and_review_claimed(self):
  records=gate.load_registry((ROOT/'docs/evidence/economic_registry_verified.json').read_bytes())
  for t in {r['case_id'] for r in records}:
   allowed,_=v42.can_emit_buy(True,True,any(r['case_id']==t and r['economic_case_closed'] is not True for r in records),False)
   self.assertFalse(allowed)
 def test_unknown_is_not_clearance(self):
  r=gate.evaluate({'ticker':'SYNTHETIC'},[],v42,candidate_sha=gate.CANDIDATE_SHA,system_live=True,decision_gate_done=True)
  self.assertFalse(r['buy_add_allowed']);self.assertIn('INDEPENDENT_ECONOMIC_CLEARANCE_MISSING',r['reasons'])
 def test_invalid_attestations_rejected(self):
  with self.assertRaises(ValueError):gate.evaluate({'ticker':'SYNTHETIC'},[],v42,candidate_sha=gate.CANDIDATE_SHA,economic_clearance='true')
  with self.assertRaises(ValueError):gate.load_registry((ROOT/'docs/evidence/economic_registry_verified.json').read_bytes()+b' ')
  with self.assertRaises(ValueError):gate.evaluate({'ticker':'SYNTHETIC'},[],v42,candidate_sha='wrong')
 def test_adapter_binds_each_case_independently_of_release_lock(self):
  records=gate.load_registry((ROOT/'docs/evidence/economic_registry_verified.json').read_bytes())
  for t in {r['case_id'] for r in records}:
   result=gate.evaluate({'ticker':t},records,v42,candidate_sha=gate.CANDIDATE_SHA,system_live=True,decision_gate_done=True,economic_clearance=True)
   self.assertFalse(result['economic_gate_allowed_under_supplied_state'])
   self.assertIn('UNRESOLVED_ECONOMIC_CASE',result['reasons'])
 def test_adapter_conflict_and_missing_clearance(self):
  for row,clearance in [({'ticker':'SYNTHETIC','debt':'CONFLICTING'},True),({'ticker':'SYNTHETIC'},False)]:
   r=gate.evaluate(row,[],v42,candidate_sha=gate.CANDIDATE_SHA,system_live=True,decision_gate_done=True,economic_clearance=clearance)
   self.assertFalse(r['economic_gate_allowed_under_supplied_state'])
 def test_release_lock_is_separate_from_economic_result(self):
  r=gate.evaluate({'ticker':'SYNTHETIC'},[],v42,candidate_sha=gate.CANDIDATE_SHA,system_live=True,decision_gate_done=True,economic_clearance=True)
  self.assertTrue(r['economic_gate_allowed_under_supplied_state']);self.assertFalse(r['buy_add_allowed'])
if __name__=='__main__':unittest.main()
