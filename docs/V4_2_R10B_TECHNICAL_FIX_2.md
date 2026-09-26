# V4.2 R10B — Technical Fix 2: fiscal-period normalization

R10B run `36267509068` fixed the SEC HTTP decompression problem:

- fetch failures: **0**
- but direct fills: **0**
- unresolved items: **349**
- all sampled unresolved items were `TARGET_PERIOD_MISSING`.

## Root cause

The frozen canonical stores SEC fiscal periods after CSV/pandas serialization in forms such as:

- `20251231.0`
- `20250630.0`

The R10B normalizer stripped every digit before validating length. Therefore
`20251231.0` became `202512310` (9 digits) and was rejected.

This is a generic serialization/parser defect. It is independent of company identity,
rank, score, or desired investment result.

## Fix

`norm_period()` now:

1. first parses numeric/float-like SEC period values;
2. requires an integer-like 8-digit YYYYMMDD representation;
3. also accepts date-like strings such as `2025-12-31`;
4. rejects malformed values.

Additional synthetic tests cover all four cases.

A sanity gate was also added: if a future R10B run returns no provenance and every unresolved
item is `TARGET_PERIOD_MISSING`, the process exits non-zero instead of producing a misleading
green run.

No XBRL concept allowlist, source priority, fiscal matching rule, model parameter,
BQS/IOS rule, G2 rule, Lane-I rule or 7+3 merge rule changed.

The previous R10B runs remain immutable evidence. R10B must be rerun as a new run.

**System remains NOT LIVE.**
