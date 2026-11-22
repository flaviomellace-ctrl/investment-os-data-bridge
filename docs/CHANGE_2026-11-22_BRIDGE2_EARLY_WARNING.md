# Modifica di sistema 22/11/2026 — BRIDGE-2 in produzione, EARLY WARNING v1.0, automazione gratuita

Approvazione: Flavio in chat, 22/11/2026 21:36 ("approvo 3 e 4. Fai anche gli altri punti").
Costituzione: proposta (messaggio delle 21:30), motivazione, approvazione umana, versione, hash, changelog.

## 1. BRIDGE-2 (punto 4) — versione dati V4.2-INTEGRATED-1.1 + BRIDGE-2
- Cosa: sinonimi XBRL standard (RevenueFromContractWithCustomerIncludingAssessedTax,
  NetCashProvidedByUsedInOperatingActivitiesContinuingOperations, WeightedAverageNumberOfShareOutstandingBasicAndDiluted)
  aggiunti in coda in bridge.py; riempimento da SEC companyfacts solo per le stesse filing già selezionate
  (companyfacts_fill.py), strettamente additivo. Attivato nel workflow settimanale update-data.yml tramite
  src/run_bridge2.py per bridge.py ed enrich_br01_br02.py, come nel replay R12-ter.
- Motivazione: copertura IOS 20-25% → 31-42% nel replay 2018-2019 e 2021-2022 (docs/r12/r12bis/BRIDGE2_DIAG_2021_2022.md).
- Shadow test: già eseguito in R12-ter (esecutore indipendente, run1 = run2). Non cambia formule, soglie o punteggi:
  aumenta solo i dati disponibili. Effetto atteso: più aziende con IOS calcolabile; la coda può cambiare
  composizione al primo aggiornamento, da registrare nel V4_2_STATO successivo.

## 2. EARLY WARNING v1.0 (punto 3)
- Cosa: src/early_warning.py, workflow early-warning.yml (giorni feriali 20:33 UTC, prima del Sentinel).
  Fonti gratuite: SEC companyfacts (trimestrali), SEC submissions (8-K e Form 4), API pubblica Nasdaq (short interest).
  Uscita: data/current/early_warning.csv.
- Soglie fisse v1.0: vedi intestazione di src/early_warning.py.
- Uso: campanelli GIALLO/ROSSO nel Daily Sentinel e nel Decision Gate (Red Team). Non modificano BQS, IOS, coda,
  soglie di ingresso o regole LIVE-LIMITATO. Azione massima generata: INVESTIGARE (ROSSO su 8-K 4.02/1.03/4.01:
  INVESTIGARE con priorità).
- Motivazione: i crolli in coda di R12 (Fossil, Signet, Alliance Data, Lululemon, Deckers) venivano da
  deterioramento successivo alla scelta, invisibile nei bilanci annuali (docs/r12/R12_PRECHECK_QUALITY_FILTER_2026-11-22.md).
- Validazione: nessun test storico (sarebbe sugli stessi dati già visti). Si misura in avanti: ogni campanello
  viene registrato con data e confrontato con l'esito a 12 e 24 mesi.

## 3. Automazione gratuita (punto 2)
- watchlist-prices.yml spostato su main (prima girava solo a mano: i workflow pianificati partono solo dal ramo principale).
- margine-data.yml (giorni feriali 05:37 UTC): src/margine_data.py porta in Python gli script del playbook
  Il Margine e scrive margine_DATA.txt, margine_RET.txt, margine_RISK.csv, benchmark_prices.csv (IMIE).
  Il Margine non dipende più dal Chrome del PC per i dati di mercato.

## Hash (sha256)
- src/bridge.py d1bbf0d14d7217f4be5f793317c32f7e000918b0b40308510d80f2ada2fc7ded
- src/companyfacts_fill.py f320e491c9b8b59c1588c3cfde9ec61ef8bd54bf4adf6888033d2ec20f9be879
- src/run_bridge2.py ffe4ec35d971d9fa21854bb5950c1e7b1163ed6edd0bfd40b8e9e02f677e789b
- src/early_warning.py 0f70942d2e4b706819a6715678c60fb422609b2b9a64ff5fe9a5391bd8fe4eed (v1.0 definitiva: tag più recente, ultimo dato depositato, TTM solo su trimestri consecutivi, vendite insider in piani 10b5-1 separate)
- src/margine_data.py b5df3966ce5442532c8c4955dc9c94c8316c50b07caaac739af4f45b94eb7765 (prima esecuzione 22/11/2026: 94/94 simboli PRESENT)

## 4. Affidabilità e semplificazione (punti 1 e 5)
- Daily Sentinel: un solo controllo serale feriale (22:24 Roma) invece di due, modello claude-sonnet-5-5 per la routine;
  legge prezzi e campanelli dal repository pubblico (il connettore GitHub non era collegato alle attività pianificate).
- Il Margine: nuova attività cloud (08:43 lunedì e giovedì) che non richiede il PC; la vecchia attività legata al PC (08:13)
  va disattivata da Flavio; nel frattempo la versione cloud ha un controllo anti-doppione.
- claude/ARCHIVIO_INDICE.md: elenco dei documenti superati che le attività non leggono più. Cancellazione dal Project
  solo dopo copia nel repository e conferma di Flavio.

## 5. Prima esecuzione in produzione (22/11/2026, run GitHub 45069111945)
S&P 500, 504 società, confronto con l'aggiornamento del 16/11 (include anche i nuovi trimestrali 2026Q3, quindi non è
solo effetto BRIDGE-2): azioni diluite presenti 371 → 485; ricavi 450 → 488; cassa operativa 487 → 499; FCF 405 → 424;
copertura media delle metriche essenziali 92,6% → 98,1%. companyfacts: 498 società lette, 0 errori, 2.593 + 7.322 voci aggiunte.
EARLY WARNING v1.0 prima esecuzione: 13 titoli, campanelli attivi su CMCSA, CHTR, JNJ (trimestrali), CHTR e TMO (8-K 5.02),
ADBE, FIX, KO, JNJ (vendite insider discrezionali). Tutti da verificare su fonte primaria prima di qualunque uso.

## 6. Strato dati "professionale" gratuito (22/11/2026, 23:00)
- Archivio point-in-time delle stime degli analisti (src/estimates_snapshot.py, workflow estimates-archive.yml,
  giorni feriali 23:52 Roma): ogni giorno la fotografia del consenso EPS (anno in corso, anno prossimo, trimestre),
  numero di analisti, prezzo obiettivo medio e giudizi, per tutto l'S&P 500 più la lista d'attesa. Fonte: API pubblica
  Nasdaq. File giornalieri in data/estimates/ (mai riscritti). È l'equivalente gratuito, costruito da oggi in avanti,
  dello storico I/B/E/S che i professionisti comprano: lo storico passato non esiste, quello futuro sì.
- EARLY WARNING v1.1: nuovo campanello STIME_GIU (consenso EPS -5% in 30 giorni o -10% in 90 giorni), attivo appena
  l'archivio ha 30 giorni di profondità (fine dicembre 2026). Stesso uso: solo INVESTIGARE.
- Controllo di salute (src/health_check.py, workflow health-check.yml, ogni giorno 07:47 Roma): se prezzi, dati
  Il Margine, campanelli, stime o fondamentali sono vecchi apre una segnalazione su GitHub, che GitHub notifica
  via email al proprietario del repository; la chiude da solo quando i dati tornano in regola.
- Hash: src/estimates_snapshot.py e src/health_check.py nel commit; src/early_warning.py v1.1 f6be23a2626bc8e81dbaa853f952e7154a0a91206c366d43e1d7427ecff8eef0.
