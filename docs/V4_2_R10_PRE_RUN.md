# V4.2 R10 — PRE-RUN INSTRUCTIONS

## Status before execution

- V4.2 engine synthetic freeze: **PASS**
- V4.2 engine SHA-256: `cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e`
- V4.2 engine MD5: `232ac18be2ada2d3a6ef97b0d4308b7b`
- V4.1 canonical SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- V4.1 frozen ranking SHA-256: `fe6aa604ca9529e2ffa53927581c509e213dc0d034072e6508a6c3ae0d1542b0`
- V4.1 frozen market snapshot SHA-256: `8d446fcdc0c6715d75746433840962dfb163874c7daccca95cad945cfdc9552d`
- System: **NOT LIVE**

## What R10 does

This is the **first real-data V4.2 engine comparison**.

It uses:
- the exact frozen V4.1 canonical fundamentals;
- the exact frozen V4.1 market snapshot;
- the already-frozen V4.2 engine;
- the already-frozen Lane-I rules.

It measures:
- IOS numerical coverage;
- matched IOS score drift;
- ranking stability;
- Top-20 / Top-10 overlap;
- generic Lane-I breadth;
- module-level aggregate changes.

## What R10 deliberately does NOT do

- no current/fresh prices;
- no validation target;
- no UBER-specific logic;
- no parameter fitting;
- no documentary BR-09 marketplace reclassification;
- no real cash-quality/commitments enrichment;
- no BUY/ADD;
- no LIVE action.

Therefore any R10 queue is diagnostic only.

## Anti-overfitting rule after execution

Once R10 runs, company names and rank movements are known.

From that point:
- the V4.2 engine cannot be altered because a particular company moved up/down;
- Lane-I thresholds and the 7+3 merge cannot be altered in-place;
- substantive changes require a new version/change request;
- technical defects may be repaired only if documented as technical defects independent of desired rankings.

## Next step after green R10

Inspect aggregate integrity first, without optimizing names.

If no critical structural regression:
complete the already-mandated real-data overlays:
1. BR-09 marketplace documentary routing/enrichment;
2. R6 cash-quality diagnostics for advancing candidates;
3. R7 commitments review for advancing candidates.

Only after those layers are operational/frozen do we prepare the new independent blind/forward validation.

**System remains NOT LIVE.**
