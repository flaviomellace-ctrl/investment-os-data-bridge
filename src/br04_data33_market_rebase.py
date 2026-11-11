"""Rebase verified fundamentals onto a pinned market snapshot; research only."""
import base64
import csv
import hashlib
import io
import json
import os
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_SHA = '5a6802101110ee3a90ef1919a04e4414d03638f9d165852cce37bcd5911666a8'
OLD_BASE_SHA = '91b0f052957e6a0a34768cfb48838bafe9d2f7f589c3ad439f95c7178e6125e2'
NEW_BASE_SHA = 'ef47d7bd3300efb0797de784d598d6caa3999869a36771ade4477ab3aa58d3ae'
ENGINE_SHA = 'cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e'
MARKET_FIELDS = ('market_price', 'market_cap', 'market_data_as_of',
                 'market_data_retrieved_at_utc', 'market_data_source',
                 'market_data_source_symbol', 'market_data_as_of_status', 'market_data_status')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read_csv(raw, columns):
    reader = csv.DictReader(io.StringIO(raw.decode(), newline=''))
    rows = list(reader)
    require(len(reader.fieldnames) == columns and len(set(reader.fieldnames)) == columns, 'schema mismatch')
    require(len(rows) == len({r['ticker'] for r in rows}) == 504, 'universe mismatch')
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), 'malformed row')
    return reader.fieldnames, rows

def rebase(candidate, old_base, new_base):
    for raw, pin in [(candidate, INPUT_SHA), (old_base, OLD_BASE_SHA), (new_base, NEW_BASE_SHA)]:
        require(sha(raw) == pin, 'input hash mismatch')
    header, rows = read_csv(candidate, 285)
    old_header, old_rows = read_csv(old_base, 212)
    new_header, new_rows = read_csv(new_base, 212)
    require(old_header == new_header, 'base schema changed')
    old = {r['ticker']: r for r in old_rows}
    new = {r['ticker']: r for r in new_rows}
    require(set(old) == set(new) == {r['ticker'] for r in rows}, 'base universe changed')
    require(all(old[t][k] == new[t][k] for t in old for k in old_header if k not in MARKET_FIELDS),
            'non-market base change requires source reconciliation')
    before = [dict(r) for r in rows]
    changes = []
    for row in rows:
        ticker = row['ticker']
        for key in MARKET_FIELDS:
            require(row[key] == old[ticker][key], 'candidate market ancestry mismatch')
            if row[key] != new[ticker][key]:
                changes.append(dict(ticker=ticker, field=key, before=row[key], after=new[ticker][key]))
            row[key] = new[ticker][key]
    require(all(a[k] == b[k] for a, b in zip(before, rows) for k in header if k not in MARKET_FIELDS),
            'fundamental amendment mutated')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode(), changes

def main():
    import importlib.util
    import sys
    import br04_economic_gate as gate
    import br04_data31_readiness as readiness
    from br04_data09_preflight import derive
    from br04_data14_market_refresh import verify_transport
    from split_for_claude import split_file

    source = ROOT/'data/research/br04-data30/RESEARCH_NOT_PROMOTED.csv'
    evidence = ROOT/'docs/evidence'
    old = zlib.decompress(base64.b64decode((evidence/'data14_base.zlib.b64').read_bytes()))
    new = zlib.decompress(base64.b64decode((evidence/'data33_market_base.zlib.b64').read_bytes()))
    baseline = (ROOT/'data/current/sp500_fundamentals.csv').read_bytes()
    raw, changes = rebase(source.read_bytes(), old, new)
    require(sha(raw) == gate.REBASED_CANDIDATE_SHA, 'output candidate hash mismatch')
    out = ROOT/'data/research/br04-data33'
    out.mkdir(parents=True, exist_ok=True)
    candidate = out/'RESEARCH_NOT_PROMOTED.csv'
    candidate.write_bytes(raw)
    transport = verify_transport(raw, out, split_file(source=candidate, output_dir=out, url_base=None))
    engine_path = ROOT/'src/investment_os/v4_2/v4_scoring.py'
    require(sha(engine_path.read_bytes()) == ENGINE_SHA, 'engine hash mismatch')
    spec = importlib.util.spec_from_file_location('data33_v42', engine_path)
    engine = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = engine
    spec.loader.exec_module(engine)
    registry = gate.load_registry((evidence/'economic_registry_verified.json').read_bytes())
    gates = Counter()
    market_status = Counter()
    decisions = []
    _, rows = read_csv(raw, 285)
    for row in rows:
        c = derive(row, engine)
        if row['ticker'] == 'IP':
            require(row['data_quality_flags'] == 'IP_MIXED_CONTINUING_DISCONTINUED_BASIS', 'IP basis guard missing')
            require(c['fcf_margin'] is None and c['net_margin'] is None, 'IP ratio suppression lost')
            c['reinvestment_rate'] = None
        bqs, coverage, _, _ = engine.bqs(c)
        ios, detail = engine.ios(c, bqs, coverage)
        gates['CALCULABLE' if ios is not None else detail.get('gate', 'UNSPECIFIED')] += 1
        market_status[row['market_data_status']] += 1
        decisions.append(gate.evaluate(row, registry, engine, candidate_sha=sha(raw)))
    readiness.CANDIDATE_SHA = sha(raw)
    historical = ROOT/'data/research/br04-data10'
    summary, qualification, differences = readiness.inventory(
        raw, (historical/'prior_rc1_ledger.csv').read_bytes(), (historical/'prior_rc1_proofs.json').read_bytes())
    for row, decision in zip(rows, qualification):
        if row['market_data_status'] != 'PRESENT' or any(readiness.number(row[k]) is None or readiness.number(row[k]) <= 0 for k in ['market_price', 'market_cap']):
            decision['reasons'].append('MISSING_OR_UNQUALIFIED_MARKET_DATA')
            decision['screen_has_open_items'] = True
    summary.update(schema='br04_data33_readiness_inventory_v1',
                   rows_with_listed_open_items=sum(q['screen_has_open_items'] for q in qualification),
                   rows_without_listed_open_items=sum(not q['screen_has_open_items'] for q in qualification),
                   open_item_counts=dict(sorted(Counter(reason for q in qualification for reason in q['reasons']).items())))
    require(sum(len(r['economic_flag_ids']) for r in decisions) == 41, 'economic binding lost')
    require(all(r['buy_add_allowed'] is False for r in decisions), 'unexpected release')
    require((ROOT/'data/current/sp500_fundamentals.csv').read_bytes() == baseline, 'production changed')
    require(sha(source.read_bytes()) == INPUT_SHA and candidate.read_bytes() == raw, 'candidate mutated')
    report = dict(schema='br04_data33_market_rebase_v1', source_commit=os.environ.get('RESEARCH_SOURCE_SHA'),
                  input_sha256=INPUT_SHA, old_market_base_sha256=OLD_BASE_SHA, market_base_sha256=NEW_BASE_SHA,
                  candidate_sha256=sha(raw), engine_sha256=ENGINE_SHA, rows=504, columns=285,
                  market_changed_cells=len(changes), fundamental_changed_cells=0, market_status=dict(market_status),
                  v42_gate_counts=dict(gates), transport=transport, bound_economic_flags=41, bound_economic_cases=10,
                  buy_add_blocked_rows=504, system_live=False, economic_clearance=False, candidate_promoted=False,
                  r11_status='NOT_EXECUTED', r12_status='NOT_EXECUTED', release_decision='BLOCKED',
                  overall_passed=True, scope='Market-only rebase, transport and V4.2 SIC-adapter compatibility; not full V4.2 overlays or independent validation.')
    files = {'report.json':report, 'market_change_ledger.json':changes, 'economic_decisions.json':decisions,
             'readiness.json':summary, 'qualification.json':qualification, 'prior_amendment_comparison.json':differences}
    for name, value in files.items():
        (out/name).write_text(json.dumps(value, indent=2)+'\n')
    manifest = {p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'manifest.json'}
    (out/'manifest.json').write_text(json.dumps(dict(files=manifest, candidate_sha256=sha(raw), release_decision='BLOCKED'), indent=2)+'\n')
    print('DATA33_REPORT='+json.dumps(report))

if __name__ == '__main__':
    main()
