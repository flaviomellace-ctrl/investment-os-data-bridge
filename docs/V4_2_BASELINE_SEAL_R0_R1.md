# INVESTMENT OS V4.2 — BASELINE SEAL (R0/R1)

- Data: **2026-09-25**
- Stato: **PASS**
- Sistema: **NOT LIVE**
- Scopo: chiudere R0/R1 prima di qualsiasi codice V4.2.

## R0 — Baseline seal

Verificati i riferimenti congelati V4.1:

- engine MD5 atteso: `68f626974592915d6c2a8e6583d6c77b`
- engine MD5 osservato: `68f626974592915d6c2a8e6583d6c77b`
- engine SHA-256 osservato: `91ce6231e8070a6fea10d2f025d3d60256ee418ff5ddeedd0215198171c13fc9`
- canonical SHA-256 da frozen receipt: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- quantitative freeze run: `36045268572`
- canonical T20 rows: `504`
- canonical T20 parts: `50`
- T20 byte-identical: `true`
- market-cap reconstructed from bridge shares: `false`
- system_live in freeze receipt: `false`

**R0 result: PASS.**

## R1 — Existing V4.1 regression suite

Eseguito `test_v4.py` contro il motore V4.1 immutato.

- test file SHA-256: `4c095a89db80b8206760f8f7c4cc817abfa1b72a14743b58f51c9c0aa38101b1`
- exit code: `0`
- PASS lines: `48`
- final marker `TUTTI I TEST PASSATI`: `true`

**R1 result: PASS.**

## Audit conclusion

V4.1 baseline è riproducibile e verde prima dello sviluppo V4.2.

Nessun ranking V4.2 eseguito.  
Nessun ticker reale usato per calibrazione.  
Nessun parametro V4.2 scelto.  
Nessun file V4.1 modificato.

**STOP CONDITION:** se in futuro engine MD5, canonical SHA o R1 non coincidono, bloccare lo sviluppo e riconciliare prima di procedere.
