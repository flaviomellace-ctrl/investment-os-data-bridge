#!/usr/bin/env python3
"""Compare a replayed fundamentals file with a reference on their common columns."""
import json, math, sys
import pandas as pd

a = pd.read_csv(sys.argv[1], dtype=str).fillna("")
b = pd.read_csv(sys.argv[2], dtype=str).fillna("")
skip = lambda c: c.startswith("market_") or c in ("weight", "sec_quarters_used")
cols = [c for c in a.columns if c in b.columns and not skip(c)]
A, B = a.set_index("ticker"), b.set_index("ticker")
common = [t for t in A.index if t in B.index]


def same(x, y):
    if x == y:
        return True
    try:
        fx, fy = float(x), float(y)
    except ValueError:
        return False
    return math.isclose(fx, fy, rel_tol=1e-9, abs_tol=1e-9)


diff = {}
examples = {}
for c in cols:
    n = 0
    for t in common:
        if not same(A.at[t, c], B.at[t, c]):
            n += 1
            examples.setdefault(c, []).append([t, A.at[t, c][:40], B.at[t, c][:40]]) if len(examples.get(c, [])) < 3 else None
    if n:
        diff[c] = n
print("PIT_COMPARE=" + json.dumps(dict(rows_replay=len(a), rows_reference=len(b), common_rows=len(common), columns_compared=len(cols),
                                       columns_only_replay=[c for c in a.columns if c not in b.columns][:40],
                                       columns_only_reference_count=len([c for c in b.columns if c not in a.columns]),
                                       columns_with_differences=len(diff), differences=diff, examples=examples)))
