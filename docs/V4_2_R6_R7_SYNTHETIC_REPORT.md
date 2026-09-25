# V4.2 R6/R7 — SYNTHETIC CASH QUALITY & COMMITMENTS REPORT

- Data: **2026-09-25**
- Stato: **PASS**
- Sistema: **NOT LIVE**
- Real-data V4.2 ranking: **NOT RUN**
- Real ticker calibration: **NONE**
- V4.1 modified: **NO**

## Scope tested

R6:
- OCF-capex-SBC owner earnings;
- missing SBC handling;
- reserve/float temporary benefit;
- temporary negative cash drag;
- incomplete normalization;
- provenance requirement;
- working-capital cash-quality flag.

R7:
- quantified commitments;
- commitments already captured in debt;
- material unquantified obligations;
- immaterial unresolved obligations;
- commitment / owner-earnings diagnostic;
- generic leverage stress including SBC;
- missing SBC;
- bank module NOT_APPLICABLE;
- nonpositive EBITDA-after-SBC.

## Result

- PASS lines: **27**
- FAIL lines: **0**
- exit code: **0**
- module SHA-256: `1d76a9a260793614edb5964b02eaed71b8b0ce6307fdb257d16773b9adb1ef3a`
- tests SHA-256: `9c91bdafb5062782d52fd3ae01887e278954e734fd6f79e4c33b0ef2b10808e9`

**R6/R7: PASS.**

## Local correction before freeze

The first local execution found a technical coding error: the module called `math.isfinite`
without importing Python's `math` module. The import was added and the suite was rerun.
No model threshold, scoring rule, diagnostic rule, or test expectation changed.

## Next gate

Dopo caricamento:
1. verificare repository;
2. eseguire R8 sector-variant regression;
3. eseguire R9 data/transport regression;
4. solo dopo preparare l'integrazione engine V4.2;
5. ancora nessun ranking reale prima del freeze del motore/adapters.
