# V4.2 R10B — Technical Fix 1: HTTP content decoding

The first R10B GitHub run (`36265893463`) completed as a GitHub Action but produced no recovery:

- queue companies: 136
- rows touched: 0
- direct fills: 0
- derived fills: 0
- fetch failures: 136
- every fetch failure: `UnicodeDecodeError`

## Root cause

The client explicitly requested:

`Accept-Encoding: gzip, deflate`

but then attempted to decode the returned response bytes directly as UTF-8 JSON.

SEC returned compressed HTTP bodies, so the compressed bytes were incorrectly passed to
`raw.decode("utf-8")`.

This is a transport/decoder defect, not a data, scoring, threshold, or model defect.

## Fix

`r10b_primary_source_recovery.py` now:

1. decodes `gzip` and `deflate` HTTP bodies before JSON parsing;
2. supports uncompressed/identity responses;
3. retries transient failures up to 3 attempts while preserving SEC fair-access spacing;
4. returns a non-zero exit code if any fetch failures remain, so a superficially green
   workflow cannot advance an incomplete candidate to R10C.

Synthetic decoder tests were added for:
- plain body;
- gzip body;
- deflate body.

No concept allowlist, fiscal-period rule, source rule, derivation formula, engine rule,
BQS/IOS parameter, Lane-I rule, or 7+3 merge rule changed.

The failed R10B run remains immutable evidence. This fix must be rerun as a new R10B run.

**System remains NOT LIVE.**
