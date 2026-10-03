"""Audit frozen-code integrity, reproducibility and residual Gate blocks.

No classification, valuation, ranking-rule or investment decision is changed.
This is development verification, not R11 or independent R12 validation.
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT / path).read_text())

def sha(path, algorithm='sha256'):
    return hashlib.new(algorithm, (ROOT / path).read_bytes()).hexdigest()

def main():
    out = Path(os.environ.get('R10M_OUTPUT', ''))
    if not str(out) or str(out) == '.':
        raise SystemExit('Explicit isolated output directory required')
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'V4_2_R10M_AUDIT_RECEIPT.json').exists():
        raise SystemExit('Refusing to overwrite audit receipt')
    manifest = read('docs/V4_2_ENGINE_MANIFEST.json')
    frozen = [
        ('v4_1_engine_md5', 'src/investment_os/v4_1_frozen/v4_scoring.py', 'md5'),
        ('v4_2_engine_sha256', 'src/investment_os/v4_2/v4_scoring.py', 'sha256'),
        ('marketplace_classifier_sha256', 'src/marketplace_classifier_v42.py', 'sha256'),
        ('inflection_lane_sha256', 'src/inflection_lane_v42.py', 'sha256'),
        ('cash_quality_commitments_sha256', 'src/cash_quality_commitments_v42.py', 'sha256'),
    ]
    integrity = []
    for key, path, algorithm in frozen:
        actual = sha(path, algorithm)
        assert actual == manifest[key], key
        integrity.append({'path': path, 'algorithm': algorithm, 'digest': actual, 'status': 'PASS'})
    suite_paths = [
        'tests/v4_1_frozen/test_v4.py', 'tests/test_marketplace_classifier_v42.py',
        'tests/test_inflection_lane_v42.py', 'tests/test_cash_quality_commitments_v42.py',
        'tests/test_sector_variants_v42.py', 'tests/test_v4_2_engine_integration.py',
    ]
    suites = []
    for path in suite_paths:
        env = dict(os.environ)
        env['PYTHONPATH'] = str(ROOT / ('src/investment_os/v4_1_frozen' if '/v4_1_frozen/' in path else 'src'))
        run = subprocess.run([sys.executable, path], cwd=ROOT, env=env, capture_output=True, text=True)
        (out / (Path(path).stem + '.log')).write_text(run.stdout + run.stderr)
        assert run.returncode == 0, path + ': ' + run.stderr
        suites.append({'path': path, 'sha256': sha(path), 'status': 'PASS',
                       'pass_check_lines': sum(line.startswith('[PASS]') for line in run.stdout.splitlines())})

    env = dict(os.environ, GITHUB_RUN_ID='R10M_REPRO')
    run = subprocess.run([sys.executable, 'src/r10c_frozen_engine_rerun.py'], cwd=ROOT, env=env, capture_output=True, text=True)
    (out / 'R10C_REPRO.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stderr
    original = ROOT / 'data/v4_2/r10c/36268612607/V4_2_R10C_FULL_COMPARISON.csv'
    reproduced = ROOT / 'data/v4_2/r10c/R10M_REPRO/V4_2_R10C_FULL_COMPARISON.csv'
    assert original.read_bytes() == reproduced.read_bytes()
    comparison_digest = hashlib.sha256(original.read_bytes()).hexdigest()
    assert comparison_digest == '7069635e5bf147ba0f8078ca4df8288fbb20f3c573d668de285caa89b83fc2c0'

    # Import the frozen engine in a fresh process to keep the audit's process isolated.
    gate_code = 'import json;from v4_scoring import can_emit_buy;print(json.dumps(can_emit_buy(True,True,True,False)))'
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src/investment_os/v4_2'))
    gate = subprocess.run([sys.executable, '-c', gate_code], cwd=ROOT, env=env, capture_output=True, text=True)
    assert gate.returncode == 0
    allowed, gate_reason = json.loads(gate.stdout)
    assert allowed is False and 'red flag' in gate_reason

    cash_path = 'data/v4_2/r10i/review_20260928/V4_2_R10I_CASH_REVIEW.json'
    br_path = 'data/v4_2/r10j/review_20261003/V4_2_R10J_BR09_REVIEW.json'
    cash = read(cash_path)
    assert sha(cash_path) == read('data/v4_2/r10i/review_20260928/V4_2_R10I_VERIFICATION_RECEIPT.json')['registry_sha256']
    br = {row['ticker']: row for row in read(br_path)['classification_reviews']}
    with (ROOT / 'data/v4_2/r10d/36303846263/V4_2_R10D_DEEP_DIVE_QUEUE.csv').open(newline='') as handle:
        queue = list(csv.DictReader(handle))
    by_ticker = {row['ticker']: row for row in cash['case_dispositions']}
    assert len(by_ticker) == len(queue) == 10 and set(by_ticker) == {row['ticker'] for row in queue}
    rows = []
    for selected in queue:
        ticker = selected['ticker']
        review = by_ticker[ticker]
        assert review['normalized_owner_earnings_usd'] is None and review['normalization_complete'] is False
        assert review['case_closed'] is False and review['buy_add_allowed'] is False
        rows.append({'ticker': ticker, 'queue_rank': int(selected['queue_rank']),
                     'selection_lane': selected['selection_lane'],
                     'disposition': 'HOLD_UNRESOLVED_NO_BUY_ADD',
                     'cash_gate': review['cash_gate'], 'confidence': review['confidence'],
                     'cash_review_reason': review['cash_review_reason'],
                     'br09_status': br[ticker]['classification_status'],
                     'normalized_owner_earnings_usd': None, 'normalization_complete': False,
                     'unresolved_material_red_flag': True, 'economic_case_closed': False,
                     'buy_add_allowed': allowed,
                     'gate_check_mode': 'HYPOTHETICAL_LIVE_AND_COMPLETED_GATE_STILL_BLOCKED_BY_RED_FLAG'})
    ledger = {'schema': 'r10m_residual_gate_ledger_v1', 'cases': rows,
              'source_cash_registry_sha256': sha(cash_path), 'source_br09_registry_sha256': sha(br_path),
              'erratum_reference': 'docs/V4_2_R10L_FIX_DA_ERRATUM.md',
              'queue_replacements': 0, 'economic_case_closures': 0,
              'r11_ready_certified': False, 'r12_performed': False, 'system_live': False}
    (out / 'V4_2_R10M_RESIDUAL_GATE_LEDGER.json').write_text(json.dumps(ledger, indent=2) + '\n')
    receipt = {'schema': 'r10m_prevalidation_integrity_v1', 'status': 'TECHNICAL_PASS_ECONOMIC_REVIEWS_OPEN',
               'frozen_integrity': integrity, 'suites': suites, 'suite_count': len(suites),
               'synthetic_check_lines_passed': sum(x['pass_check_lines'] for x in suites),
               'r10c_reproduction_byte_identical': True, 'r10c_comparison_sha256': comparison_digest,
               'historical_universe_rows': 504, 'gate_blocked_case_count': len(rows),
               'independent_validation': False, 'R11_performed': False, 'R12_performed': False,
               'engine_modified': False, 'ranking_rules_modified': False, 'system_live': False,
               'audit_script_sha256': sha('src/r10m_prevalidation_integrity.py')}
    (out / 'V4_2_R10M_AUDIT_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ['status','suite_count','synthetic_check_lines_passed','r10c_reproduction_byte_identical','gate_blocked_case_count','R11_performed','R12_performed','system_live']}, indent=2))

if __name__ == '__main__':
    main()
