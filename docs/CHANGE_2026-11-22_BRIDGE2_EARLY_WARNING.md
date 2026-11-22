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
- src/early_warning.py bebcbb5b7c113a57ad5d43bc6798e74565da0294226e6c94d49f4d81af361af4
- src/margine_data.py vedi commit (aggiornato dopo la prima esecuzione se necessario)
