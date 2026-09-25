# V4.2 R4/R5 — INFLECTION LANE & GROWTH BAKE-OFF REPORT

- Data: **2026-09-25**
- Stato: **PASS**
- Sistema: **NOT LIVE**
- Real-data V4.2 ranking: **NOT RUN**
- Real ticker calibration: **NONE**
- V4.1 modified: **NO**

## R4 — Synthetic inflection archetypes

Otto archetipi sintetici:
1. genuine inflection;
2. mature compounder;
3. one-off fake inflection;
4. working-capital/float cash boost;
5. cyclical rebound;
6. dilution-funded growth;
7. revenue growth without cash conversion;
8. cash growth with declining revenue.

La Lane I:
- promuove ad high-confidence solo la genuine inflection;
- non confonde il mature compounder con un'inflection;
- mantiene one-off / cash-quality / cyclical cases PROVISIONAL;
- respinge dilution-funded, no-cash e declining-revenue cases.

## R5 — Growth-treatment bake-off

Pre-registered synthetic behavior score:
- G0 V4.1 baseline: **5/8**
- G1 blended: **2/8**
- G2 guarded per-share: **8/8**

Selezionato: **G2_GUARDED_PER_SHARE**.

Formula:
`g = min(max(revenue_cagr3, 0), max(fcf_per_share_cagr3, 0), 0.15)`

La formula è stata scelta senza ranking reale e non è ancora integrata nel frozen engine.

## Merge

Deep-dive queue congelata a:
- 7 Lane V;
- 3 Lane I;
- deterministic dedupe;
- Lane V backfill se Lane I insufficiente.

## Test result

- PASS lines: **22**
- FAIL lines: **0**
- exit code: **0**
- lane source SHA-256: `c45dbb85558919358a727c0dbe3d657d9cd9a41ea6987a51289374af69b55c3a`
- tests SHA-256: `b933c2d4fec7a9c3c774b618ad48bf2d9fe64d8ea63f2236c010249c275183f6`

**R4/R5: PASS.**

## Note on test correction

A first local run contained one incorrect expected assertion in the backfill test:
with 7 valuation names + 1 Lane-I name, the two valuation backfills are `V8` and `V9`,
not `V9` and `V10`. The implementation behavior was correct; the test expectation was corrected
before freeze. No production rule or parameter changed.

## Next

R6/R7:
- quality-of-cash diagnostics;
- off-balance/commitments gate;
- missing/provenance rules;
- synthetic tests.

Solo dopo R6/R7 si potrà preparare l'integrazione del motore V4.2.
