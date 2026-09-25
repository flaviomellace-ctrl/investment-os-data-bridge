# V4.2 LANE I + GROWTH TREATMENT FREEZE

- Data: **2026-09-25**
- Stato: **FROZEN BEFORE REAL-DATA V4.2 RANKING**
- Sistema: **NOT LIVE**
- Lane module SHA-256: `c45dbb85558919358a727c0dbe3d657d9cd9a41ea6987a51289374af69b55c3a`
- Test SHA-256: `b933c2d4fec7a9c3c774b618ad48bf2d9fe64d8ea63f2236c010249c275183f6`

## 1. Lane I — Economic Inflection

Lane I è price-independent e non emette BUY/ADD.

### Eligibility floors

- BQS >= **60**
- owner earnings > **0**
- revenue CAGR 3y >= **5%**
- FCF CAGR 3y >= **15%**
- FCF/share CAGR 3y >= **12%**
- cash conversion >= **0.75**
- share change <= **+3%**

I flag di one-off, cash-quality o cyclical rebound non vengono ignorati:
un candidato può risultare economicamente eleggibile ma resta **PROVISIONAL** e non entra
nella Lane I high-confidence finché il flag non è riconciliato.

### Ranking Lane I

Solo candidati `HIGH_CONFIDENCE`.

Ordine:
1. inflection score DESC;
2. BQS DESC;
3. FCF/share CAGR3 DESC;
4. entity key ASC.

Inflection score:
- revenue trajectory: 25 punti;
- FCF trajectory: 30;
- FCF/share trajectory: 30;
- cash conversion: 10;
- share discipline: 5.

Il punteggio serve solo a ordinare candidati già eleggibili.

## 2. Deep-dive merge rule

Totale massimo: **10**

- Lane V (IOS): **7 posti**
- Lane I: **3 posti**
- dedupe deterministico;
- se Lane I ha meno di 3 high-confidence names, backfill da Lane V a partire dal rank 8;
- nessuna sostituzione discrezionale dopo aver visto i nomi.

## 3. Growth-treatment bake-off

Tre formule sono state confrontate solo su 8 archetipi sintetici.

- `G0_V41_BASELINE`: `min(max(revenue_cagr3,0),10%)`
- `G1_BLENDED`: 40% revenue + 30% FCF + 30% FCF/share, input capped 25%, output capped 15%
- `G2_GUARDED_PER_SHARE`: `min(max(revenue_cagr3,0), max(fcf_per_share_cagr3,0), 15%)`

Risultati sui comportamenti pre-registrati:
- G0: **5/8**
- G1: **2/8**
- G2: **8/8**

### Decisione R5

**G2_GUARDED_PER_SHARE è il trattamento selezionato come candidato V4.2.**

Motivazione economica:
- riconosce più del 10% solo quando crescita dei ricavi e crescita della cassa per azione concordano;
- non premia crescita di ricavi senza cassa;
- non premia crescita di cassa senza crescita del business;
- incorpora indirettamente la diluizione tramite FCF/share;
- cap massimo 15%;
- con input necessario MISSING restituisce MISSING, non zero.

**Importante:** questa decisione NON modifica ancora `v4_scoring.py`.
L'integrazione nel motore avverrà solo dopo R6/R7 e con una policy esplicita per input MISSING/CONFLICTING.
Fino ad allora V4.1 resta intatto.

## 4. Anti-overfitting attestation

- ticker reali nel codice/test: **0**
- ranking reale V4.2 eseguito: **NO**
- UBER o altri validation target usati per parametri: **NO**
- V4.1 modificato: **NO**
- BQS weights modificati: **NO**
- IOS 30/25/20/15/10 weights modificati: **NO**

Dopo il primo ranking reale V4.2, questa lane/merge/growth decision non può essere ritoccata in-place
per migliorare nomi o ranking. Un eventuale cambiamento sostanziale richiederà V4.3 change control.

**END — FROZEN PRE-REAL-DATA**


## Freeze note — local test assertion correction

Before this freeze, one local regression assertion expected the wrong valuation backfill pair.
The code correctly produced `V8, V9`; the test had expected `V9, V10`.
Only the test expectation was corrected. No Lane-I threshold, quota, scoring rule,
growth formula, or merge implementation changed.
