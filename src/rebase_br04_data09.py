"""Reconstruct a pinned research candidate. Never writes canonical/staging data."""
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

INPUT_SHA = 'e108b517924ceced165d356874b5e0a4598ec9a103d452f034ff4431ab34f9e0'
MANIFEST_SHA = '046a14230ee2336e190e2c31a6a5297227accd74acec4151fab2ec03d80cc1e6'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def reconstruct(data, manifest_bytes):
    require(sha(data) == INPUT_SHA, 'input byte hash mismatch')
    require(sha(manifest_bytes) == MANIFEST_SHA, 'manifest byte hash mismatch')
    manifest = json.loads(manifest_bytes)
    reader = csv.DictReader(io.StringIO(data.decode(), newline=''))
    header = reader.fieldnames
    before = list(reader)
    require(len(header) == len(set(header)) == 285 and len(before) == 504, 'shape')
    require(len({r['ticker'] for r in before}) == 504, 'duplicate ticker')
    after = [dict(r) for r in before]
    by = {r['ticker']: r for r in after}
    for ticker, identity in manifest['filings'].items():
        require(all(by[ticker][k] == v for k, v in identity.items()), 'filing identity')
    edits = set()
    for change in manifest['changes']:
        t, k = change['ticker'], change['field']
        require(t in manifest['filings'] and k in header[212:], 'edit scope')
        require((t, k) not in edits, 'duplicate edit')
        require(by[t][k] == change['before'], 'old value mismatch')
        edits.add((t, k))
        by[t][k] = change['after']
    differences = {(a['ticker'], k) for a, b in zip(before, after) for k in header if a[k] != b[k]}
    require(differences == edits and len(edits) == 75, 'whole-file scope')
    require(all(a[k] == b[k] for a, b in zip(before, after) for k in header[:212]), 'legacy preservation')
    for t in manifest['filings']:
        r = by[t]
        require(r['total_debt_status'] == r['br04_status'] == 'PARTIAL', 'partial scope')
        require(r['bs_closure_residual_pct'] == next(x for x in before if x['ticker'] == t)['bs_closure_residual_pct'], 'closure preserved')
        for kind in ['finance', 'operating']:
            k = kind + '_lease_liabilities'
            if r[k]:
                require(kind.upper() + '_LEASE_MISSING' not in r['br04_flags'].split(';'), 'stale lease flag')
    for t in ['CVX', 'MET']:
        r = by[t]
        debt, cash, ocf = float(r['total_debt']), float(r['cash_and_equivalents']), float(r['annual_operating_cash_flow'])
        require(float(r['net_debt']) == debt - cash, 'net debt arithmetic')
        require(r['net_debt_to_ocf_lb'] == format((debt-cash)/ocf, '.15g'), 'lower bound arithmetic')
        require(float(r['net_debt_to_ocf_lb']) < 3 < float(r['net_debt_to_ocf_ub']), 'indeterminate bounds')
        require(r['net_debt_to_ocf'] == '' and r['ios_leverage_indeterminate'] == 'true', 'no exact leverage')
    for t in ['JPM', 'USB', 'STT']:
        r = by[t]
        require(r['net_debt_to_ocf'] == 'NOT_APPLICABLE' and r['ios_leverage_indeterminate'] == 'false', 'bank module convention')
        require('BANK_FUNDING_PERIMETER_UNRESOLVED' in r['br04_flags'], 'bank funding gate')
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=header)
    writer.writeheader()
    writer.writerows(after)
    result = buffer.getvalue().encode()
    report = dict(schema='br04_data09_reconstruction_v1', input_sha256=sha(data), output_sha256=sha(result), manifest_sha256=sha(manifest_bytes), rows=504, columns=285, changed_cells=len(edits), changed_rows=5, unchanged_rows=499, legacy_columns_preserved=212, br04_status=dict(Counter(r['br04_status'] for r in after)), leverage_indeterminate=sum(r['ios_leverage_indeterminate']=='true' for r in after), source_quarters_preserved=True, regression_s2_for_new_hash=False, transport_s3_for_new_hash=False, engine_s4_for_new_hash=False, independent_review_completed=False, economic_clearance=False, candidate_promoted=False, buy_add_allowed=False, system_live=False)
    return result, report

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / 'data/research/br04-data09'
    candidate, report = reconstruct(args.input.read_bytes(), (directory/'manifest.json').read_bytes())
    (directory/'RESEARCH_NOT_PROMOTED.csv').write_bytes(candidate)
    (directory/'reconstruction.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
