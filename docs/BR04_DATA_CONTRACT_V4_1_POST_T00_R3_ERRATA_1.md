# BR-04 DATA CONTRACT V4.1 POST-T00 R3 — ERRATA 1

Data: 2026-09-23

Documento interessato:
`BR04_DATA_CONTRACT_V4_1_POST_T00_R3`

## Natura dell'errata

Questa errata è esclusivamente formale e di coerenza del test BR04-T30.

Il documento R3 originale resta immutato e conservato come evidenza storica.

Nessuna formula economica, soglia, gerarchia, regola sul debito,
regola sulla cassa, regola sugli interessi, regola settoriale,
peso BQS/IOS o comportamento del motore V4.1 viene modificato.

## Correzione BR04-T30

Nel §12, la definizione:

> le righe senza `annual_adsh` sono esattamente quelle riportate da T00 (8)

è sostituita, ai fini operativi e di audit, da:

> le righe senza `annual_adsh` sono esattamente quelle riportate dal
> T00-bis eseguito sulla stessa base canonica pinned del candidato,
> con conteggio per righe societarie e non per numero di ADSH unici.

Per la base canonica:

`c95e356632182dddd85b002a552eefa83da27264838617d8661af895fbb69594`

il valore corretto è:

`companies_without_annual_adsh = 5`

Il precedente valore T00 = 8 non è più utilizzato come criterio di BR04-T30.

Il valore 8 derivava dal precedente censimento e non rappresenta
il conteggio corretto delle righe societarie prive di `annual_adsh`.

## Evidenza applicabile al candidato BR-04

Candidate SHA-256:

`56e61f56231dc2b6eda742874847aa4210407ab76a6f6cbfbfcadc2e7fdaeead`

Per questo candidato:

- righe senza `annual_adsh` nel T00-bis v1.2: 5
- righe senza `annual_adsh` nel candidato: 5
- flag `NO_ANNUAL_ADSH`: 5

Pertanto BR04-T30 è PASS secondo il criterio corretto.

## Effetti sulla catena di test

L'errata non modifica il candidato, il canonico o il motore.

Non modifica:
- `base_canonical_sha256`
- `candidate_sha256`
- MD5 di `v4_scoring.py`

L'implementazione già utilizzata da BR04-T30 applicava il criterio
qui formalizzato.

Questa errata deve essere considerata parte integrante del contratto R3
per le successive fasi S5, S6, S7 e per T31.
