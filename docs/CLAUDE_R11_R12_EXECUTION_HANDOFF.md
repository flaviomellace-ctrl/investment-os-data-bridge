# R11/R12 — esecuzione con Claude

Stato 2026-11-08: preflight tecnico disponibile; R11 e R12 NON ESEGUITI.
Queste istruzioni non sono ricevute di validazione.

## Materiali per il solo preparatore (chat A)

Repository: https://github.com/flaviomellace-ctrl/investment-os-data-bridge
Commit implementazione: 25a945f525a308d68f70b6db91481ed562d77aff
Pacchetto DATA33: https://github.com/flaviomellace-ctrl/investment-os-data-bridge/actions/runs/42500695328/artifacts/13625457671
Piano normativo interno: docs/V4_2_REGRESSION_PLAN.md
Stato prerequisiti: docs/R11_R12_PREPARATION_STATUS.md
Manifest storico: docs/V4_2_ENGINE_MANIFEST.json (synthetic freeze, NON manifest completo dell'integrazione attuale).
SHA candidato: e7f69c5c8d54c232687f4e63ee1056994ce6960031af04096f92600843688f51
SHA motore V4.2: cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e

Il preparatore può vedere materiale di sviluppo. Non può poi essere l'esecutore R12.
DATA33 è un controllo con adapter SIC e soppressione dei rapporti IP non omogenei: non sostituisce la pipeline integrata con overlay.
Il pacchetto DATA33 non deve essere inviato automaticamente all'esecutore blind.

## Prompt da usare nella chat A — preparatore e custode

Agisci come preparatore indipendente e custode delle prove R11/R12 di Investment OS.
Leggi il piano e i materiali identificati sopra. Non dichiarare R11/R12 PASS sulla base della CI.
Lavora sul commit esatto, senza modificare formule o soglie per ottenere risultati desiderati.

1. Verifica hash, dipendenze, suite e prerequisiti R0-R10; identifica precisamente ciò che la CI attesta e ciò che non attesta.
2. Ricostruisci e congela il pacchetto integrato eseguibile (motore, adapter, classificatore, lane, cash-quality, commitments, overlay e Decision Gate). Non chiamare integrato il solo motore. Verifica che sia riproducibile.
3. Prepara nuovi controlli R11 sealed/non-current, separati dagli esempi di sviluppo e dai target noti. Congela input, esiti attesi, rubriche e soglie PRIMA dell'esecuzione. Registra la provenienza: se sono nuovi, non attribuire loro una preregistrazione storica.
4. Conserva separatamente la chiave degli esiti attesi. Produci R11_EXECUTOR_INPUT.zip senza tale chiave, un manifest SHA-256 e un comando di esecuzione. Non dare accesso al custode e all'esecutore attraverso la stessa chat.
5. Per R12 prepara separatamente frozen artifacts e metodologia sicura, senza nomi target, classifiche, risultati storici, conversazioni o attese dei test. Mantieni riservato il validation set e la sua chiave. Definisci prima la soglia, la procedura di apertura e cosa viene congelato prima dell'apertura.
6. Produci un elenco FINITO di eventuali prerequisiti bloccanti con file o evidenza esatta richiesta. Non richiedere indiscriminatamente di completare tutti i dati delle 504 aziende.
7. Nessuna operatività LIVE o ordine. Un titolo escluso non equivale a un rilievo economico risolto.

Consegna i pacchetti realmente creati e verificati, non nomi di file ipotetici. Se non puoi eseguire codice o accedere ai materiali, dichiaralo esplicitamente.

## Chat B — esecutore R11

Aprire una chat nuova, fuori da progetti con memoria o allegati di sviluppo.
Allegare esclusivamente R11_EXECUTOR_INPUT.zip e manifest del preparatore.
Prompt: "Verifica il manifest ed esegui il protocollo R11 congelato senza modificare codice, input o scoring. Non cercare la chiave degli esiti attesi. Restituisci ambiente, log, output grezzi, eccezioni e hash dei risultati. Non dichiarare PASS senza confronto con la chiave custodita separatamente."

Riportare output e hash alla chat A: il custode applica la rubrica congelata, produce R11_RECEIPT con PASS/FAIL e prove caso per caso.
Errore critico => stop all'ammissibilità R12; nessuna modifica post-risultato non documentata.

## Chat C — esecutore R12

Solo dopo R11 e prerequisiti ammissibili. Nuova chat indipendente anche da B.
Non condividere questa guida completa, il repository di sviluppo, la chat A/B, DATA33 o precedenti classifiche. Condividere solo il pacchetto sicuro e il prompt seguente.

Prompt: "Sei l'esecutore indipendente di una validazione blind. Usa soltanto gli artefatti congelati e la metodologia allegata. Verifica hash e ambiente. Prima di aprire il validation set produci il freeze richiesto dal protocollo, con hash e log; rispetta l'ordine delle fasi. Non modificare formule, soglie o selezione dei casi. Non cercare risultati precedenti o chiavi attese. Restituisci output immutabili, log, hash, eccezioni e limiti. Se manca un input necessario, indica esattamente quale; non dichiarare una prova eseguita."

Il custode apre il set nella fase prevista, confronta risultati con chiave e soglie preregistrate e produce R12_RECEIPT.
Una nuova chat riduce la contaminazione da conversazione; non garantisce assenza di conoscenze pregresse nel modello. Documentare separazione, accessi e limiti.

## Rientro e decisione

Riportare R11_RECEIPT, R12_RECEIPT, manifest e log effettivi.
Verificare che gli hash corrispondano alla stessa integrazione e che non vi siano tuning successivi.
Esiti insufficienti non si convertono in PASS per compromesso.
Esiti conformi consentono di valutare Bootstrap/IPS e dry-run operativo con broker automatico OFF; non autorizzano automaticamente trading reale.
