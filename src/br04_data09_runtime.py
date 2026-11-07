"""Custody and frozen runtime for research-only DATA09 transport/preflight."""
import base64
import hashlib
import json
import re
from pathlib import Path
from audit_br04_data09 import CANDIDATE_SHA

RECEIPT = 'docs/evidence/br04-data09/research_regression_40212402168.json'
RECEIPT_SHA = '00867b87d0d1a9b46e0b395ea53be1fbeede0a151dfcd6ffc00eee5ab0801fd6'
RUNTIME_PINS = {
    'V4_SCORING_B64': ('v4_scoring.py', '91ce6231e8070a6fea10d2f025d3d60256ee418ff5ddeedd0215198171c13fc9'),
    'TEST_V4_B64': ('test_v4.py', '4c095a89db80b8206760f8f7c4cc817abfa1b72a14743b58f51c9c0aa38101b1'),
}

def approved_regression(root):
    raw=(root/RECEIPT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=RECEIPT_SHA:
        raise ValueError('S2 research receipt hash mismatch')
    receipt=json.loads(raw);r=receipt['report']
    if not (r['phase']=='S2_RESEARCH' and r['overall_passed'] is True and r['candidate_sha256']==CANDIDATE_SHA and not r['failed_tests'] and not r['failed_gates'] and r['candidate_promoted'] is False and r['buy_add_allowed'] is False):
        raise ValueError('S2 research custody not approved')
    return r

def restore_runtime(root):
    source=(root/'.github/workflows/br04-s4-engine-preflight.yml').read_text()
    directory=root/'data/research/br04-data09/runtime'
    decoded={}
    for key,(filename,pin) in RUNTIME_PINS.items():
        match=re.search(r'^\s*'+key+r':\s*[\'\"]?([A-Za-z0-9+/=]+)',source,re.M)
        if not match:raise ValueError('Frozen runtime missing: '+key)
        data=base64.b64decode(match.group(1),validate=True)
        if hashlib.sha256(data).hexdigest()!=pin:raise ValueError('Frozen runtime hash mismatch: '+key)
        decoded[filename]=data
    directory.mkdir(parents=True,exist_ok=True)
    for filename,data in decoded.items():(directory/filename).write_bytes(data)
    return directory

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    approved_regression(root)
    restore_runtime(root)
    print('Research S2 receipt and frozen runtime SHA-256 verified')
