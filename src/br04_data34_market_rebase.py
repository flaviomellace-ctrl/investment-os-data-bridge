#!/usr/bin/env python3
"""DATA34: market-only rebase of the DATA33 research candidate onto the 2026-11-09 current base. Research only.

Fundamentals are byte-preserved. The step refuses to run if the two bases differ outside the market fields.
"""
import argparse, csv, hashlib, io, json
from pathlib import Path

INPUT_SHA = 'e7f69c5c8d54c232687f4e63ee1056994ce6960031af04096f92600843688f51'
OLD_BASE_SHA = 'ef47d7bd3300efb0797de784d598d6caa3999869a36771ade4477ab3aa58d3ae'
NEW_BASE_SHA = 'b5cd5a7f8d36c34b48f1639be3b6373abe320c87d7e1b347bf9151046f0d5c8e'
NEW_BASE_COMMIT = '757e2d31c5f7d9895b1349a3223bc4e609c05307'
MARKET_FIELDS = ('market_price', 'market_cap', 'market_data_as_of', 'market_data_retrieved_at_utc', 'market_data_source',
                 'market_data_source_symbol', 'market_data_as_of_status', 'market_data_status')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def read(raw, columns):
    reader = csv.DictReader(io.StringIO(raw.decode(), newline=''))
    rows = list(reader)
    require(len(reader.fieldnames) == columns and len({r['ticker'] for r in rows}) == len(rows) == 504, 'schema or universe mismatch')
    return reader.fieldnames, rows


def rebase(candidate, old_base, new_base):
    for raw, pin in ((candidate, INPUT_SHA), (old_base, OLD_BASE_SHA), (new_base, NEW_BASE_SHA)):
        require(sha(raw) == pin, 'input hash mismatch')
    header, rows = read(candidate, 285)
    oh, orows = read(old_base, 212)
    nh, nrows = read(new_base, 212)
    require(oh == nh, 'base schema changed')
    old, new = {r['ticker']: r for r in orows}, {r['ticker']: r for r in nrows}
    require(set(old) == set(new) == {r['ticker'] for r in rows}, 'universe changed')
    require(all(old[t][k] == new[t][k] for t in old for k in oh if k not in MARKET_FIELDS), 'non-market base change requires source reconciliation')
    changes = 0
    for row in rows:
        for k in MARKET_FIELDS:
            require(row[k] == old[row['ticker']][k], 'candidate market ancestry mismatch')
            changes += row[k] != new[row['ticker']][k]
            row[k] = new[row['ticker']][k]
    out = io.StringIO(newline='')
    w = csv.DictWriter(out, fieldnames=header); w.writeheader(); w.writerows(rows)
    return out.getvalue().encode(), changes


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for a in ('candidate', 'old-base', 'new-base', 'out'):
        p.add_argument('--' + a, required=True)
    a = p.parse_args()
    raw, changes = rebase(*(Path(x).read_bytes() for x in (a.candidate, a.old_base, a.new_base)))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'DATA34_RESEARCH_NOT_PROMOTED.csv').write_bytes(raw)
    report = dict(schema='br04_data34_market_rebase_v1', input_sha256=INPUT_SHA, old_market_base_sha256=OLD_BASE_SHA,
                  market_base_sha256=NEW_BASE_SHA, market_base_commit=NEW_BASE_COMMIT, candidate_sha256=sha(raw), rows=504, columns=285,
                  market_changed_cells=changes, fundamental_changed_cells=0, candidate_promoted=False, buy_add_allowed=False,
                  system_live=False, sec_independent_reread='NOT_EXECUTED',
                  scope='Market-only rebase. Known fundamental defects are NOT corrected here: they are bound as open data conflicts in the evidence file.')
    (out / 'data34_report.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report))
