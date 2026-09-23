# BR-04 DATA CONTRACT V4.1 POST-T00 R3 — ERRATA 2

Data: 2026-09-23

Documento interessato:
`BR04_DATA_CONTRACT_V4_1_POST_T00_R3`

## Natura dell'errata

Questa errata risolve esclusivamente una sovrapposizione tra la regola
generale §7.4 per il debito `CONFLICTING` e le regole settoriali
specifiche per `roic`.

Il documento R3 originale resta immutato e conservato come evidenza storica.

Questa errata NON modifica:

- il motore `v4_scoring.py`;
- pesi BQS o IOS;
- formule;
- soglie;
- moduli;
- definizione del debito;
- regole di cassa;
- regole sugli interessi;
- candidate SHA già prodotti.

## 1. Precedenza delle regole settoriali su `roic`

Nel §7.4 la regola:

> quando `total_debt = CONFLICTING`, `roic` riceve `CONFLICTING`

si applica esclusivamente ai moduli nei quali `roic` è una metrica
applicabile.

Le regole settoriali specifiche hanno precedenza.

Pertanto:

### BANK

`roic = NOT_APPLICABLE`

come già previsto dal §10.1.

### INSURANCE

`roic = NOT_APPLICABLE`

come già previsto dal §10.3.

### Altri moduli

Quando `total_debt_status = CONFLICTING` e `roic` è normalmente
applicabile:

`roic = CONFLICTING`.

## 2. BR04-T16

BR04-T16 resta invariato.

Deve continuare a verificare:

- BANK:
  - `net_debt_to_ocf = NOT_APPLICABLE`
  - `interest_coverage = NOT_APPLICABLE`
  - `roic = NOT_APPLICABLE`

- INSURANCE:
  - `roic = NOT_APPLICABLE`

al 100% delle righe dei rispettivi moduli.

## 3. Effetto su §7.4

Per INSURANCE resta invece pienamente applicabile la regola §7.4 relativa a:

- `total_debt` vuoto quando lo stato è `CONFLICTING`;
- conservazione dei candidati in `total_debt_candidates`;
- uso del candidato di debito più alto per il valore prudenziale di
  `net_debt_to_ocf`, quando cassa e OCF consentono il calcolo;
- flag `DEBT_CONFLICTING_PRUDENTIAL_VALUE`.

La sola eccezione settoriale riguarda `roic`,
che resta `NOT_APPLICABLE`.

Per BANK continuano a prevalere integralmente le regole del §10.1.

## 4. Semantica di `DEBT_CONFLICTING_PRUDENTIAL_VALUE`

Il flag `DEBT_CONFLICTING_PRUDENTIAL_VALUE` indica che, in presenza di
debito `CONFLICTING`, il candidato di debito più alto è stato selezionato
come base prudenziale.

Il flag può quindi restare presente anche quando il rapporto finale
`net_debt_to_ocf` non è pubblicabile per una regola settoriale o per la
mancanza di un input necessario.

Quando invece:

- il modulo consente `net_debt_to_ocf`;
- la cassa è disponibile;
- l'OCF è disponibile;
- esiste almeno un candidato di debito;

il valore prudenziale deve essere effettivamente pubblicato secondo §7.4.

## 5. Effetto sul nuovo test BR04-T32

BR04-T32 dovrà verificare:

- per moduli diversi da BANK e INSURANCE:
  `roic = CONFLICTING` quando `total_debt_status = CONFLICTING`;

- per INSURANCE:
  `roic = NOT_APPLICABLE`;

- per BANK:
  restano applicabili le regole settoriali del §10.1.

Questa errata elimina quindi l'ambiguità tra §7.4, §10.3 e BR04-T16.

## 6. Nessuna modifica retroattiva dei risultati

Questa errata formalizza la precedenza già applicata dal candidate builder
e già verificata da BR04-T16.

Non modifica il candidato corrente.

La successiva patch del builder relativa a `net_debt_to_ocf` §7.4
costituirà invece una modifica del candidato e richiederà un nuovo
`candidate_sha256` e la riesecuzione della catena prevista.
