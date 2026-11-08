# Perimetro di utilizzo — ricerca sullo snapshot DATA33

Data: 2026-11-08. Decisione: utilizzare il pacchetto verificato per ricerca e controllo dei dati. Non costituisce rilascio LIVE o validazione della strategia.

## Risultato verificato

Commit di implementazione: 25a945f525a308d68f70b6db91481ed562d77aff.
Candidato SHA-256: e7f69c5c8d54c232687f4e63ee1056994ce6960031af04096f92600843688f51.
Run remoto: https://github.com/flaviomellace-ctrl/investment-os-data-bridge/actions/runs/42500695328
Pacchetto: https://github.com/flaviomellace-ctrl/investment-os-data-bridge/actions/runs/42500695328/artifacts/13625457671

Research regression, current-base compatibility, economic gate regression e smoke test: PASS sul commit indicato.
504 righe, 285 colonne; 1.508 celle mercato aggiornate, nessuna modifica ai fondamentali durante DATA33.
Trasporto: 51 parti, ricostruzione identica byte per byte.
41 rilievi economici su 10 casi collegati; 504 righe bloccate per BUY/ADD.
501 righe con stato mercato PRESENT, 3 MISSING. PRESENT non certifica la freschezza per operazioni future.
Il controllo locale V4.2 con adapter SIC produce 201 IOS calcolabili; calcolabilità non significa opportunità di investimento o approvazione economica.

## Cosa si può fare adesso

- Consultare i dati del pacchetto e la loro provenienza.
- Leggere qualification.json, readiness.json ed economic_decisions.json per distinguere valori mancanti, conflitti e rilievi aperti.
- Riprodurre il controllo di compatibilità e il trasporto.
- Usare i risultati come materiale di ricerca, senza interpretarli come raccomandazioni operative.

Il pacchetto non comprende una piattaforma di paper trading né una simulazione di portafoglio validata. Non pubblicare classifiche o suggerimenti BUY/ADD come se fossero validati.
Il motore e le evidenze restano congelati; nuovi snapshot richiedono nuovamente i controlli pertinenti.

## Condizioni finite per l'operatività reale

1. Per ciascun titolo da rendere azionabile, chiudere i rilievi materiali con evidenze oppure escluderlo dall'universo azionabile. L'esclusione non deve essere registrata come risoluzione del rilievo.
2. Completare i prerequisiti del piano V4_2_REGRESSION_PLAN.md, compresi artefatti congelati e comparazione richiesta. La diagnostica DATA33 non sostituisce la pipeline completa V4.2 con overlay.
3. Eseguire R11 su controlli riservati separati dal target noto, con scoring preregistrato.
4. Eseguire R12 in ambiente indipendente, senza conversazione di sviluppo né precedente validazione, congelando il risultato prima dell'apertura del validation set e applicando la soglia preregistrata.
5. Solo dopo gli esiti richiesti: Bootstrap/IPS e verifica operativa del Decision Gate, con esecuzione automatica del broker disattivata.

Non è richiesto riempire ogni campo di tutte le 504 aziende per concludere la fase di ricerca. Non estendere la raccolta generale dei dati come prerequisito implicito al suo utilizzo.
R11 e R12: NOT_EXECUTED. Le relative prove e l'attestazione indipendente non sono presenti nel pacchetto DATA33.
Nessuna approvazione storica viene trasferita automaticamente al nuovo candidato.

## Limite della decisione

Questo documento chiude il perimetro di ricerca sopra descritto, non l'intero progetto di investimento.
Non modifica formule, soglie, gate, dati di produzione, stato LIVE o autorizzazioni agli ordini.
