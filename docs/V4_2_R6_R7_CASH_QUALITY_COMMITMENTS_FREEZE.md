# V4.2 R6/R7 — CASH QUALITY & COMMITMENTS FREEZE

- Data: **2026-09-25**
- Stato: **FROZEN BEFORE REAL-DATA V4.2 RANKING**
- Sistema: **NOT LIVE**
- Module SHA-256: `1d76a9a260793614edb5964b02eaed71b8b0ce6307fdb257d16773b9adb1ef3a`
- Test SHA-256: `9c91bdafb5062782d52fd3ae01887e278954e734fd6f79e4c33b0ef2b10808e9`

## R6 — Quality of cash

Principi congelati:

- reported owner earnings = `OCF - capex - SBC`;
- OCF, capex e SBC sono tutti obbligatori;
- MISSING non diventa mai zero;
- normalizzazioni positive temporanee di cassa vengono sottratte;
- drag temporanei documentati possono essere aggiunti indietro;
- normalized owner earnings viene emesso solo con provenance completa e `normalization_complete=true`;
- adjustment assoluto >= **10%** del reported owner earnings è material;
- material adjustment o cash-quality flag => IOS confidence almeno `PROVISIONAL` + `RECONCILE_CASH_QUALITY`;
- R6 è diagnostico: non cambia automaticamente il punteggio IOS.

Classi diagnostiche incluse:
- reserve/float contribution;
- tax timing;
- working-capital anomaly;
- noncash revaluation flag.

## R7 — Off-balance commitments

Per ogni candidato avanzato registrare:
- purchase obligations;
- take-or-pay / off-take;
- long-term capacity/content/fleet commitments;
- guarantees;
- leases non già catturati nel debt;
- altri fixed claims materialmente pertinenti.

Regole:
- già incluso nel debt => escluso dal totale per evitare double count;
- material + MISSING/unquantified => `INVESTIGARE` e `PROVISIONAL`;
- quantified uncovered obligations sono riportate e confrontate con owner earnings;
- nessuna capitalizzazione automatica nell'IOS in questa fase;
- immaterial unresolved item non genera blocco automatico.

## Secondary leverage stress

Aggiunte tre viste diagnostiche per moduli non finanziari:
- gross debt / EBITDA;
- net debt / EBITDA;
- gross debt / (EBITDA - SBC).

Interpretazione secondaria congelata:
- <3.0x => BELOW_CAUTION;
- >=3.0x e <4.0x => CAUTION;
- >=4.0x => HIGH;
- denominator <=0 => INDETERMINATE;
- BANK/INSURANCE => NOT_APPLICABLE in questo generic stress view.

Questa vista NON sostituisce la metrica primaria V4.1.

## Anti-overfitting attestation

- real ticker in code/tests: **0**
- real-data V4.2 ranking executed: **NO**
- BQS weights changed: **NO**
- IOS weights changed: **NO**
- V4.1 changed: **NO**
- BUY/ADD emitted: **NO**

**END — R6/R7 FROZEN PRE-REAL-DATA**


## Freeze note — technical correction

Before this freeze, the first local execution failed because Python's `math` module had not
been imported while `math.isfinite` was used. The import was added and the complete suite
was rerun successfully. No economic rule, threshold, scoring weight, or test expectation changed.
