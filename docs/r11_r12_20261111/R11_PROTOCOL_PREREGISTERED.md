# R11 — Hidden-control regression. Protocollo preregistrato

Control set: `R11-HC-20261111-A`. Congelato l'11 novembre 2026, PRIMA di qualsiasi esecuzione.
Stato: **NON ESEGUITO**. Sistema: **NOT LIVE**. Nessun BUY/ADD.

## Provenienza (dichiarata)

I controlli sono NUOVI: creati l'11 novembre 2026 dal preparatore/custode. Non esisteva alcun set R11
precedente e non viene rivendicata alcuna preregistrazione storica. Criteri, soglie ed esiti attesi sono
stati fissati in questa data, prima dell'esecuzione, e non sono stati ottenuti eseguendo la pipeline sui controlli.

## Che cosa viene eseguito

La pipeline integrata V4.2 congelata (`src/v42_integrated_pipeline.py`) sui 45 casi del file
`controls/r11_control_cases.json` (61 entità sintetiche, esercizio di riferimento FY2024, non correnti).
Componenti e hash sono in `R11_MANIFEST_SHA256.json`. Ogni caso è eseguito due volte per provare il determinismo.

I casi sono sintetici: nessuna impresa reale, nessun ticker reale, nessun target noto, nessun esempio
tratto dalle suite di sviluppo. Coprono le regole R2–R9 del piano di regressione: routing marketplace,
invarianza di presentazione, MISSING≠0, market cap non ricostruito, conflitti di dato, varianti settoriali,
archetipi di inflessione, qualità della cassa, impegni, controlli negativi, Decision Gate, coda 7+3.

## Ruoli

- Esecutore: verifica il manifest, esegue `run_r11.sh`, restituisce output grezzo, log, ambiente e hash.
  Non valuta, non modifica nulla, non cerca la chiave.
- Custode: detiene la chiave degli esiti attesi, separata da questo pacchetto e dal repository.
  Applica la rubrica congelata e produce `R11_RECEIPT`.

Impegno crittografico sulla chiave (SHA-256 del file sigillato, che contiene un nonce casuale):

    9c4be9d0c38d759c317062ccdba83d842bcae91d4ed3afe0bad9d2d671bafa3a

## Rubrica e soglie (congelate)

Severità secondo `V4_2_REGRESSION_PLAN.md` §3. Controlli: 130 puntuali (55 CRITICAL, 75 MAJOR) più 5 globali CRITICAL.

- CRITICAL: 100% richiesto. Un solo fallimento = R11 FAIL e stop all'ammissibilità R12.
- MAJOR: 100% richiesto.
- MINOR: nessun controllo MINOR nel set; tolleranza massima 2 se ne venissero rilevati di formato.
- Globali: nessuna eccezione; determinismo; `buy_add_allowed=false` e `system_live=false` su ogni entità;
  hash di componenti, orchestratore, runner e file dei controlli uguali al manifest; hash dell'output uguale a quello dichiarato dall'esecutore.

Nessuna rivalutazione dopo il risultato. Se il custode dimostra che un esito atteso contraddice la specifica
scritta congelata, la prova è INCONCLUSIVA e richiede un nuovo set sigillato: non diventa mai PASS.

## Limiti dichiarati

1. Controlli sintetici: verificano regole, gate e routing, non la qualità predittiva su imprese reali
   né la scansione documentale di filing reali.
2. L'orchestratore di integrazione è stato scritto dal custode nella stessa sessione in cui ha definito i controlli.
   L'indipendenza riguarda i cinque moduli congelati e l'esecuzione, non l'autore dell'integrazione.
3. R11 PASS non è R12, non è validazione della strategia e non autorizza operatività.
