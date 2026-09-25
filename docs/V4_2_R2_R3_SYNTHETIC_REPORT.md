# V4.2 R2/R3 — SYNTHETIC MARKETPLACE TEST REPORT

- Data: **2026-09-25**
- Stato: **PASS**
- Sistema: **NOT LIVE**
- Real-data ranking eseguito: **NO**
- Ticker reali usati nei test: **NO**
- BQS/IOS weights modified: **NO**
- V4.1 modified: **NO**

## Artifacts

- `src/marketplace_classifier_v42.py`
  - SHA-256: `c4031e77f9baf8347b7c07f82decb8bf0e6b2209bae3d9f21c06c7a61b92d170`
- `tests/test_marketplace_classifier_v42.py`
  - SHA-256: `d49adb5a9f330c87cbfb970ec8a334785a9100835db1b60da79829a9ea89e579`

## R2 — Synthetic marketplace routing

Coperti:
- true two-sided marketplace;
- SaaS con linguaggio "platform" ma senza economia marketplace;
- principal-inventory economics;
- agency/network economics;
- evidenza documentale incompleta;
- fonte primaria obbligatoria;
- definition drift;
- MISSING handling;
- scope mismatch;
- cohort-only retention;
- assenza di ticker/company-name nell'API di classificazione.

## R3 — Presentation invariance

Verificato che la sola differenza di presentazione contabile su margini revenue-based
non cambia gli input marketplace destinati al motore:
`ebitda_on_volume`, `fcf_on_volume`, `take_rate`, `cash_conversion`.

La presentazione contabile resta diagnostica, non routing/scoring input.

## Result

- PASS lines: **19**
- FAIL lines: **0**
- exit code: **0**

**R2/R3: PASS.**

## Next gate

Se PASS:
1. caricare questi artefatti nel repository;
2. non eseguire ancora ranking V4.2;
3. procedere a R4/R5: inflection synthetic archetypes + growth-treatment bake-off;
4. congelare la Lane I prima del primo real-data ranking V4.2.
