# Risposta al REQUEST_CHANGES della revisione separata 0.5

Versione: Sviluppo 0.6 · 2026-10-06 · Per il riesame nella stessa chat del revisore.
Testo della revisione ricevuto: `evidence/RELAZIONE_REVISIONE_SEPARATA_0_5_RICEVUTA.txt`. Sonde: `review_probes/`.

Lo SHA-256 esterno dello ZIP 0.6 viene comunicato nella chat, fuori dal pacchetto. Quello della 0.5 era `efbc4740dd2649a82bed2021ff11a5a66f02820a2dbaee865a3ac12c1cf134b3`: coincide con il valore calcolato dal revisore.

## Problemi medi

| ID | Richiesta | Correzione | Test | Mutanti |
|---|---|---|---|---|
| M1 | VERIFIED deve esigere la lista di scarico fissata e tutte le 57 chiavi | L'hash della lista (`551d38fd…dba43`) è fissato nel codice e nel contratto e confrontato con la ricevuta. Le 57 chiavi (33 R13, 4 R14 di cui 1 in comune, 21 R20) devono essere tutte presenti come FETCHED o ABSENT; altrimenti la composizione è rifiutata e nulla viene scritto. Il numero 57 è fissato nel contratto. | 6 (`test_M1_*`) | M1a–M1i |
| M2 | R14 deve usare il fatto del filing della riga anche se diverso; definire la precedenza | Se il filing della riga riporta il periodo con valore identico: invariata. Con valore diverso: sostituita da quel fatto (`REPLACED_BY_ROW_FILING_FACT`). Svuotata solo se il filing della riga non riporta il periodo, o lo riporta in modo contraddittorio o non positivo. Precedenza scritta nel contratto (sotto). | 11 (classe `R14`) | M2a–M2l |
| M3 | Con esercizio provato e nessun fatto diretto, svuotare sempre | La cella viene svuotata e i derivati ricalcolati qualunque sia il valore memorizzato. Vale anche quando i filing sulla stessa base sono in disaccordo o il filing della riga si contraddice. La condizione «coincide con un fatto riportato» è stata eliminata. | 3 (`test_M3_*`) più 4 test esistenti aggiornati | M3a–M3e |

### Precedenza fra R14 e R13 (contratto, `precedence`)

1. R14 gira per primo.
2. R13 giudica poi la cella così come R14 l'ha lasciata. Dove R13 raggiunge un verdetto (KEEP, REPLACE o EMPTY) quel verdetto è finale, anche su un esito R14.
3. Dove R13 non riesce a provare l'esercizio (UNVERIFIABLE), vale l'esito R14.
4. Una cella vuota nella **base** non viene mai riempita. Una cella svuotata da R14 non è una cella vuota di base: R13 può scrivervi il suo fatto diretto.
5. I derivati si calcolano per ultimi, dal testo finale dei loro ingressi.

Sul controesempio CTAS del revisore: `prior_diluted_shares` diventa il fatto del filing della riga e `diluted_shares_yoy` viene ricalcolato. Nella 0.5 entrambi si svuotavano.

Scelta fatta in R14 e da valutare: il periodo è riconosciuto con fine identica e inizio entro 7 giorni da quello della provenienza. Con l'inizio esatto, nella sonda del revisore R14 svuotava e poi R13 ripristinava; l'esito finale era lo stesso, ma per FOX, FOXA, PG e PH, fuori ambito R13, una differenza di un giorno sull'inizio avrebbe svuotato la cella.

### Cosa M3 non copre

Le celle in ambito il cui esercizio **non** è provato (catena interrotta o ambigua, periodo fuori tolleranza, esercizio della riga assente dal suo filing) restano come R14 le ha lasciate, con stato UNVERIFIABLE. Ora sono contate nella ricevuta (`in_scope_cells_left_unverifiable`) e il misuratore elenca le righe e segnala quali sono in coda. Nell'anteprima il caso è uno: CTAS FY-3. La resa della catena sui dati reali resta ignota, come nota il revisore.

## Indurimenti

| ID | Correzione | Test | Mutanti |
|---|---|---|---|
| B1 | Un payload con il marcatore `PREVIEW_NOT_SEC_BYTES` è rifiutato in VERIFIED; in PREVIEW il marcatore è obbligatorio. `origin` resta una dichiarazione: il contratto lo dice. | 4 | B1a–B1c, F22 |
| B2 | Rifiutate come symlink la cartella dei payload e `raw/`. | 1 | B2a, B2b |
| B3 | JSON non valido, struttura errata e ricevute malformate diventano `CORRECTION_BLOCKED` con uscita 1. Ogni altro errore: `CORRECTION_BLOCKED: UNEXPECTED_…` con uscita 2, senza traceback e senza file. | 3 | B3a–B3d |
| B4 | Ogni modulo, se importato da un interprete senza `-B`, rimuove il proprio bytecode appena scritto e disattiva la scrittura per i successivi. La frase della 0.5 era imprecisa: ora la proprietà è verificata da un test su tutti i moduli. | 1 | — |

## Divergenze minori

| Osservazione | Intervento |
|---|---|
| Ambito R20: condizione `A!=B` in più nel caso «FY-3 vuoto» | Tolta dal codice; il conteggio resta 22 |
| «PENDING è un candidato, vuoto» | Corretto: PENDING non è un candidato. Il file si chiama `PENDING_IDENTICAL_TO_ACCEPTED_NOT_A_CANDIDATE.csv` |
| `inferred_values_written: 0` era una costante | Sostituito da due misure: scritture controllate contro il loro fatto e scritture senza fatto. Ogni REPLACE o FILL deve essere esattamente il testo del valore del fatto citato; controllato alla scrittura e di nuovo prima della ricevuta |
| `rank_candidate.py` accettava qualunque file e un'etichetta libera | Ora misura una cartella di composizione: modo ed etichetta vengono dalla ricevuta, file e registro devono corrispondere ai loro hash. Niente più `--label` |
| Concetto dell'estremo annuale (nota al punto 5) | Recepito come diagnostica: se il payload dell'altro concetto è presente e il filing della riga riporta a FY0 un ricavo diverso, la riga è marcata `…CONCEPT_CHOICE_OPEN`. Nessuna cella cambia; le chiavi non sono obbligatorie. In anteprima: CEG marcato, KEYS no |
| `verify_manifest.py`: cartella vuota non elencata, radice come symlink | Entrambe rifiutate |

## Workflow

| Osservazione | Intervento |
|---|---|
| Controllo che fallisce in silenzio | Tolto `continue-on-error`. Uscita 0: tutto confermato. Uscita 1: righe non confermate, run verde con avviso. Uscita 2 o più: errore tecnico, run rosso. Il riepilogo riporta l'esito con un nome distinto |
| 404 non ritentato | Un 404 diventa assenza solo dopo due risposte 404. Le chiavi assenti sono elencate nel riepilogo |
| Fine riga | `v43_sec_verify/.gitattributes` con `* -text`. La lista resta byte-identica alla 0.5 |
| `VERIFICATION.csv` senza hash | Hash nel risultato del confronto, nel riepilogo e in `VERIFICATION.sha256` |
| `github_sha` e `github_run_id` | Riportati nel riepilogo del run e nella ricevuta di composizione |
| Azioni per tag | **Non fatto.** Non posso verificare da qui gli hash dei commit; un hash trascritto male fermerebbe il run. Resta da fare da parte tua |

Compatibilità: un artifact prodotto con il drop-in 0.5 resta utilizzabile, perché la lista di scarico e lo schema della ricevuta non sono cambiati. Il drop-in 0.6 cambia `facts.py` e `sec_payloads.py`, quindi `PINS.sha256` e l'hash nel workflow.

## Non recepito o ancora aperto

- Azioni GitHub fissate per commit.
- Resa della catena di contiguità sui dati SEC reali.
- Scala d'unità di MCD (punto D5).
- La ricevuta di composizione non è autenticata: il misuratore la lega ai file, non ne certifica l'origine.
- Campagna di mutazione scritta a mano, non esaustiva; la copertura resta sottile (vedi relazione).
- Workflow e scarico SEC mai eseguiti da me.
