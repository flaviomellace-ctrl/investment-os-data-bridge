"""Research-only economic gate adapter. Does not grant R11/R12 or release approval."""
import hashlib,json
REGISTRY_SHA='9428786994c547e739f7e4742f9c02ebcb392bc3706c3a81af7d787c0a16ba96'
CANDIDATE_SHA='5a6802101110ee3a90ef1919a04e4414d03638f9d165852cce37bcd5911666a8'
def load_registry(raw):
 if hashlib.sha256(raw).hexdigest()!=REGISTRY_SHA:raise ValueError('economic registry hash mismatch')
 records=json.loads(raw)['records']
 if len(records)!=41 or len({r['case_id'] for r in records})!=10:raise ValueError('economic registry scope mismatch')
 return records

def evaluate(row,records,engine,*,candidate_sha,system_live=False,decision_gate_done=False,economic_clearance=False):
 """Join archived unresolved cases to rows before calling the frozen decision gate.
 No absence-of-flag inference: independent economic clearance must be explicit.
 This adapter intentionally cannot enable live operation on this research release.
 """
 if candidate_sha!=CANDIDATE_SHA:raise ValueError('candidate hash mismatch')
 if any(type(x) is not bool for x in [system_live,decision_gate_done,economic_clearance]):raise ValueError('strict booleans required')
 cases=[r for r in records if r['case_id']==row['ticker']]
 unresolved=any(r.get('economic_case_closed') is not True for r in cases)
 conflict=any(v=='CONFLICTING' for v in row.values())
 reasons=[]
 if unresolved:reasons.append('UNRESOLVED_ECONOMIC_CASE')
 if conflict:reasons.append('DATA_CONFLICT')
 if not economic_clearance:reasons.append('INDEPENDENT_ECONOMIC_CLEARANCE_MISSING')
 economic_allowed,economic_reason=engine.can_emit_buy(system_live,decision_gate_done,unresolved or not economic_clearance,conflict)
 allowed,reason=engine.can_emit_buy(False,decision_gate_done,unresolved or not economic_clearance,conflict)
 assert allowed is False
 return {'ticker':row['ticker'],'economic_flag_ids':[r['flag_id'] for r in cases if r.get('economic_case_closed') is not True],'reasons':reasons+['RELEASE_NOT_VALIDATED'],'buy_add_allowed':allowed,'system_live':False,'engine_reason':reason,'economic_gate_allowed_under_supplied_state':economic_allowed,'economic_gate_reason':economic_reason}
