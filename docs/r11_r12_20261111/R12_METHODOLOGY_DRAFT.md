# R12 — Nuova validazione blind/forward. Metodologia in bozza (11 novembre 2026)

Stato: BOZZA NON AMMESSA. Nulla qui è preregistrato finché le decisioni D1–D5 non sono approvate e congelate con hash.

## Oggetto
Verificare, su un insieme mai visto dallo sviluppo, che la pipeline integrata V4.2 congelata
(`frozen_artifacts/`, hash in `R12_PRELIMINARY_MANIFEST.json`) produca coda di approfondimento ed esiti di
Decision Gate coerenti con le regole, senza conoscere esiti attesi, target o classifiche precedenti.

## Ruoli
- Custode: congela validation set e chiave; non esegue. Ha letto materiale di sviluppo.
- Esecutore R12: sessione indipendente, fuori dal Project, che riceve solo il pacchetto sicuro. Non riceve la chiave.

## Sequenza freeze/apertura
1. Prerequisito: R11 PASS con ricevuta.
2. Il custode congela il validation set (dati + regole di raccolta delle evidenze), calcola gli hash, definisce e sigilla la chiave con nonce; pubblica solo l'impegno SHA-256.
3. L'esecutore verifica il manifest ed esegue una sola volta, senza modifiche.
4. FREEZE: l'esecutore consegna output grezzo e SHA-256 dell'output. Da questo istante l'output non è modificabile.
5. APERTURA: solo dopo il punto 4 il custode apre la chiave e applica la rubrica congelata.
6. Ricevuta R12 con esito, hash, ambiente, eccezioni. Nessuna rivalutazione; un difetto della chiave rende la prova inconclusiva.

## Criteri di valutazione (proposta)
- CRITICAL 100%: nessun BUY/ADD; nessun conflitto di dato silenziato; MISSING mai trattato come zero;
  market cap mai ricostruito; variante settoriale corretta; determinismo; hash conformi; nessun controllo negativo reso eleggibile.
- MAJOR: instradamento marketplace corretto sui casi con evidenza primaria; controlli negativi di inflessione non in alta confidenza;
  coda 7+3 conforme alla regola di fusione.
- Componente forward: le idee emerse sono registrate nel ledger di validazione forward e valutate a 1, 3, 5 anni.
  Non è condizione di superamento di R12 e non autorizza operatività.

## Vincoli sui dati
- Nuove acquisizioni solo in snapshot separati con fonte, endpoint, periodo, unità, valuta, timestamp, ritardo.
- Nessuna informazione successiva alla data simulata nei test storici. Universo point-in-time quando applicabile.
- Evidenze documentali solo da fonte primaria; l'assenza di evidenza resta NOT_REVIEWED e blocca.

## Decisioni che richiedono approvazione prima del congelamento
- D1 Composizione del validation set: (a) solo forward su snapshot corrente nuovo; (b) casi storici point-in-time appaiati
  (successi e fallimenti) con dati alla data simulata; (c) entrambi. Numero di entità e criteri di inclusione.
- D2 Soglie di superamento per i controlli MAJOR e regola per i casi inconclusivi.
- D3 Leasing operativo MISSING nel candidato: lasciarlo fuori dagli impegni (comportamento attuale) oppure trattarlo come impegno materiale non quantificato.
- D4 Ratifica delle cinque regole del livello di integrazione (INT-1…INT-5) descritte nel rapporto di esecuzione.
- D5 Base dati: DATA33 poggia sulla base corrente del 2 novembre; il ramo principale è già a una base successiva. Decidere se ribasare prima di R12.

## Cosa non fa R12
Non attiva LIVE, non sostituisce IPS, Decision Gate a tre analisi indipendenti, clearance economica indipendente.
