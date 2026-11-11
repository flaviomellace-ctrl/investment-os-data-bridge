# Investment OS V4.2 — Rapporto di esecuzione, 11 novembre 2026

Stato: RESEARCH / VALIDATION ONLY. NOT LIVE. BUY/ADD bloccato. R11 NON eseguito. R12 NON ammesso.
Modello effettivo della sessione: `claude-fable-5-2` (configurato; Opus 5.5 non selezionato in questa sessione).

## 1. Accesso e ambiente

| Voce | Esito |
|---|---|
| Repository, ramo `research/br04-data09-current-base` | Clonato in sola lettura. Testa del ramo `3f1b2e1` (solo documentazione dopo `25a945f`). |
| Commit DATA33 `25a945f…` | Presente; usato per ricostruire il candidato. |
| Motore V4.2 | SHA-256 `cbdb4e24…8ed6e` verificato. |
| Motore V4.1 congelato | MD5 `68f62697…` verificato. |
| Pacchetto DATA33 (artifact 13625457671) | NON scaricabile: GitHub richiede autenticazione per gli artifact e l'accesso con credenziali al repository è stato negato. Sostituito dalla ricostruzione locale. |
| Candidato DATA33 | Ricostruito byte per byte dalla catena del commit `25a945f`: 504 righe, SHA-256 `e7f69c5c…8f51` uguale a quello dichiarato. |
| Rilettura SEC indipendente (`regress_br04_candidate.py --research-data09 --historical-base`) | NON rieseguita: richiede il secret `SEC_CONTACT_EMAIL` e rete verso sec.gov, non disponibili nella sandbox. Per sbloccare la catena è stato usato un segnaposto dichiarato, derivato dalla ricevuta archiviata 40212402168; non attesta nulla ed è escluso dai pacchetti. |
| Scrittura sul repository | NON disponibile. Il ramo `claude/v42-integrated-freeze-r11` esiste solo in locale ed è consegnato come bundle git. |
| Python | 3.13.18 e 3.12.3: output identico. Nessuna dipendenza esterna per pipeline, test di integrazione e R11. |
| Claude for Financial Advisors | Non presente tra gli strumenti della sessione. Non usato. |
| Alpha Vantage MCP | Non installato né autorizzato. Non usato. |
| FMP | Collegato, ma l'endpoint dei bilanci è negato dal piano in uso. Non usato. |
| SEC EDGAR | Raggiunto solo tramite il browser integrato (API XBRL companyfacts). Snapshot `SEC-RECON-20261111`. |

## 2. Integrazione ricostruita

Nel repository non esisteva un esecutore unico della catena completa: lo script R10D è legato a candidati precedenti e alla rete.
Ho aggiunto `src/v42_integrated_pipeline.py`, che compone senza modificarli motore, adapter SIC, classificatore BR-09,
Lane I, cash-quality/commitments e gate del motore. I cinque moduli sono caricati solo a hash conforme.

Esito su DATA33 (504 righe, registro dei 41 rilievi, nessuna evidenza documentale fornita):
- conteggi dei gate IOS identici al diagnostico DATA33 (201 calcolabili);
- coda 7+3 composta da 10 entità; `buy_add_allowed` falso su 504 righe;
- SHA-256 del risultato `dac54549…eddce`, riprodotto da copia pulita.

### Difetto tecnico dimostrato e corretto
L'adapter recuperato (`br04_data09_preflight.derive`) non passa al motore `opinc_yoy` e `net_income_series`, che l'adapter
originale del freeze V4.1 (run 36045268572) passava. Effetto: le guardie `BASE_EFFECT_SUSPECTED` e `PRIOR_YEAR_ONE_OFF_SUSPECTED`
non scattavano mai. Correzione nell'orchestratore, con le definizioni originali. Prova su DATA33: BQS e IOS invariati su tutte le 504 righe;
117 righe ora segnalate; Lane I in alta confidenza da 57 a 46; coda invariata. Nessuna formula o soglia modificata.

### Difetto di riproducibilità (non corretto, documentato)
`regress_v42_r8_r9.py` legge `data/current`, che nel frattempo è cambiato: sul ramo attuale restituisce BLOCK.
Rieseguito sull'albero dati del commit della ricevuta (`f0dee5a`) restituisce PASS.

### Scelte nuove del livello di integrazione (da ratificare, non preregistrate storicamente)
- INT-1 Evidenza documentale assente: modulo originale e stato PROVISIONAL (piano R2, caso 5).
- INT-2 Triage negativo con segnali ignoti che potrebbero ribaltarlo: PROVISIONAL, non negativo documentato.
- INT-3 Overlay senza evidenza: NOT_REVIEWED e blocco; l'assenza di revisione non vale come esito pulito.
- INT-4 Inventario degli impegni non attestato come completo, flag di qualità non revisionati, dati di mercato non PRESENT, caso economico aperto, clearance indipendente assente: blocco.
- INT-5 Guardia dei rapporti a base mista attivata dal flag di qualità del dato, non dal ticker (stesso risultato del diagnostico DATA33).

## 3. Test eseguiti

| Prova | Esito |
|---|---|
| Suite unittest del repository al commit `25a945f` | 86 test, OK |
| Suite unittest sul ramo di integrazione | 101 test, OK |
| Motore V4.2, integrazione sintetica | 34 PASS, 0 FAIL |
| R2/R3 classificatore marketplace | 19 PASS, 0 FAIL |
| R4/R5 Lane I | 22 PASS, 0 FAIL |
| R6/R7 cash-quality e impegni | 27 PASS, 0 FAIL |
| R8 varianti settoriali | 21 PASS, 0 FAIL |
| R1 suite V4.1 congelata | tutti i test passati |
| Test di integrazione dell'orchestratore | 15 test, OK (3.12 e 3.13) |
| Catena DATA09→DATA33 offline | 26 passi con esito 0; candidato finale a hash conforme |
| Riproduzione del pacchetto da copia pulita | OK, hash conforme |

Log in `logs/`.

## 4. Prerequisiti R0–R10

| Fase | Verifica odierna |
|---|---|
| R0 | MD5 motore V4.1, canonico V4.1 `d2207e92…`, cartella del run 36045268572: verificati. Hash del risultato blind `dcc2b650…`: NON verificabile, nessun file del repository lo produce. |
| R1 | Rieseguito: PASS. |
| R2–R7 | Rieseguiti: PASS. |
| R8 | Rieseguito: PASS. |
| R9 | PASS solo sull'albero dati del commit `f0dee5a`; non rieseguibile sul ramo attuale. |
| R10 | Ricevute R10…R10P presenti; hash degli output dichiarati coerenti. Riguardano candidati precedenti: nessuna approvazione trasferita a DATA33. Confronto V4.1/V4.2 su base DATA30 presente solo come diagnostico. |
| Output del piano | Presente solo `V4_2_ENGINE_MANIFEST.json`. Mancano con quel nome: REGRESSION_RECEIPT, SYNTHETIC_TEST_REPORT, V41_COMPARISON, FREEZE_RECEIPT, BLIND_HANDOFF. |

## 5. Rilievi economici

41 rilievi su 10 casi: **0 risolti con prova, 41 ancora aperti, 0 titoli esclusi dall'operatività**.
Per 5 rilievi BR-09 (GM, TROW, NEM, FIX, ANET) il solo quesito marketplace ha esito negativo documentato in archivio; il caso resta aperto.
Dei 64 riferimenti del registro, 31 sono nel repository con hash conforme; 33 rimandano a file di revisione esterna non presenti (pacchetto `archived_case_records`).
Dettaglio in `ECONOMIC_FINDINGS_REGISTER_20261111.csv`.

Riconciliazione con i 10-K (XBRL, stessa accessione della riga DATA33), 13 imprese × 6 voci: 61 coincidenze. Differenze:
- GM: ricavi del candidato 167.971 mln contro 185.019 mln consolidati (il candidato usa il solo tag dei contratti con clienti). SBC assente nel candidato, 334 mln nel filing.
- FOX: l'utile del candidato (1.727 mln) include le interessenze di terzi; attribuibile agli azionisti 1.685 mln. La revisione d'archivio dichiara base FY2025, la riga DATA33 è FY2026.
- Leasing operativo: assente nel candidato e presente nel filing per 9 imprese su 13, tra cui una per 25.069 mln. Oggi il leasing mancante non entra negli impegni.
- ANET: valore attuale del leasing non etichettato nel filing; pagamenti non attualizzati 90,5 mln.

Tre entità della coda integrata DATA33 non hanno alcuna istruttoria economica nel registro. Tre casi del registro sono fuori dalla coda attuale: non è un'esclusione.
`market_data_as_of` è vuoto su tutte le righe: la freschezza del dato di mercato non è certificabile.
Il ramo principale ha già una base dati successiva (`b5cd5a7f…`, 9 novembre) rispetto a quella su cui poggia DATA33 (`ef47d7…`).

## 6. R11

Control set `R11-HC-20261111-A`: 45 casi, 61 entità sintetiche non correnti, 130 controlli (55 CRITICAL, 75 MAJOR) più 5 globali.
Criteri, soglie ed esiti attesi fissati prima dell'esecuzione, dalle specifiche scritte, senza eseguire la pipeline sui controlli.
Controlli nuovi: nessuna preregistrazione storica rivendicata.
- File dei controlli: SHA-256 `6505a6004143127d9daff72ba9f20a49e0261f1630a6b2f77b90c506866928c0`
- Impegno sulla chiave: SHA-256 `9c4be9d0c38d759c317062ccdba83d842bcae91d4ed3afe0bad9d2d671bafa3a`
- Runner ed esecuzione provati solo su un esempio di sviluppo; lo scorer provato solo con una chiave fittizia.

Limite: controlli sintetici e orchestratore scritto dal custode nella stessa sessione.

## 7. Cosa manca

1. Esecuzione R11 in sessione indipendente e ricevuta del custode.
2. Decisioni D1–D5 per R12 e ratifica di INT-1…INT-5.
3. Evidenze primarie per i 41 rilievi e istruttoria delle tre entità di coda non coperte.
4. Rilettura SEC indipendente del candidato in CI (non rieseguita qui).
5. Pubblicazione del ramo di integrazione (bundle fornito).
6. Correzione dei dati del candidato emersi dalla riconciliazione: richiede un nuovo candidato, non una modifica di DATA33.
