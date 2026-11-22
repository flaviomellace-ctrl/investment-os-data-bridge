# Contratti di correzione R13 · R14 · R20 — proposta 0.6

Stato: **PROPOSTA rivista dopo il REQUEST_CHANGES della revisione separata 0.5, non approvata.** Modifiche rispetto alla 0.5: completezza dei payload in VERIFIED, regola R14, precedenza fra clausole, regola che svuota in R13. Testo normativo: `R13_R14_R20_CONTRACT.json` (fissato per hash nel codice). Questo documento lo spiega; in caso di divergenza vale il JSON.

Base: composto accettato Staging 0.3 (`e7f23e87…d495a`), letto in sola lettura. V4.2, motore congelato, `data/current` e pacchetti accettati non vengono toccati.

## Fonte dei fatti

- Unica fonte: payload JSON grezzi `companyconcept` della SEC, elencati con SHA-256 in una ricevuta il cui hash viene fissato a riga di comando.
- Il registro estratto da modello (`SEC_FACTS_LEDGER.csv`) **non è una fonte**: serve solo a confrontare le attese.
- Senza payload (modalità PENDING) nessuna cella cambia: l'uscita è byte-identica alla base e **non è un candidato**.
- **Modalità VERIFIED**: la ricevuta deve dichiarare la lista di scarico fissata (`551d38fd…dba43`) e contenere tutte le 57 chiavi che le tre clausole interrogano (33 per R13, 4 per R14 di cui 1 in comune, 21 per R20), ciascuna come scaricata o come assente alla SEC. Altrimenti la composizione è rifiutata.
- `origin` e il marcatore d'anteprima sono dichiarazioni: tengono le anteprime fuori da VERIFIED, non certificano l'autenticità. Quella poggia sul run del workflow e sull'hash della ricevuta.

## Clausola di calendario (vale per R13 e R20)

Un fatto è utilizzabile solo se supera **tutte** queste condizioni:

1. **Form annuale** (10-K, 20-F, 40-F).
2. **Durata annuale**: fra 350 e 378 giorni.
3. **Esercizio provato per struttura**, mai per etichetta: l'esercizio della riga deve comparire nel filing della riga stessa; gli esercizi precedenti si raggiungono camminando all'indietro su periodi annuali contigui (inizio = fine precedente + 1 giorno), con un solo periodo possibile a ogni passo. I campi `fy`, `fp`, `frame` non vengono mai letti.
4. **Tolleranza di calendario**: la fine del periodo così trovato deve cadere entro 7 giorni dal periodo normalizzato della riga.

La tolleranza da sola non seleziona mai un fatto: un periodo che finisce entro 7 giorni ma non è contiguo, o non ha durata annuale, è respinto.

## Precedenza fra le clausole

1. R14 gira per primo.
2. R13 giudica poi la cella così come R14 l'ha lasciata. Dove R13 raggiunge un verdetto (conferma, sostituzione o svuotamento) quel verdetto è finale, anche su un esito R14.
3. Dove R13 non riesce a provare l'esercizio, vale l'esito R14.
4. Una cella vuota nella base non viene mai riempita da R13 o R14. Una cella svuotata da R14 non è una cella vuota di base: R13 può scrivervi il suo fatto diretto.
5. Poi R20; i derivati per ultimi, dal testo finale dei loro ingressi.

## R14 — disponibilità alla data del filing

- Ogni fatto usato da qualunque clausola deve essere depositato entro la data `annual_filed` della riga.
- Ambito: le 10 celle recuperate da un filing successivo a quello della riga.
- Periodo: quello della provenienza, come riportato dal filing della riga (stessa fine, inizio entro la tolleranza di calendario).

| Il filing della riga… | Esito |
|---|---|
| riporta il periodo con lo stesso valore | cella invariata; fonte riattribuita al filing della riga |
| riporta il periodo con un valore diverso | cella **sostituita** dal fatto del filing della riga |
| riporta due valori o due periodi diversi, o un valore non positivo | cella svuotata |
| non riporta il periodo (o il concetto è assente alla SEC) | cella svuotata |

## R13 — azioni diluite su base omogenea

- Ambito: le 33 righe selezionate dallo screening congelato del revisore.
- Campi: azioni annuali, precedenti, FY-1, FY-2, FY-3.
- **Base della riga**: la base di esposizione del filing della riga.
- **Fatto diretto**: il fatto riportato dal filing della riga; oppure da un filing annuale non successivo che concorda con il filing della riga, entro lo 0,5%, su **ogni** periodo annuale che entrambi riportano (almeno uno).
- Valore memorizzato entro lo 0,5% dal fatto diretto: testo invariato. Oltre: sostituito dal fatto diretto.
- **Nessun valore inferito**: se l'esercizio è provato e non esiste un fatto diretto utilizzabile sulla base della riga, la cella diventa vuota (MISSING) e i derivati vengono ricalcolati, **qualunque sia il valore memorizzato**. Vale anche se i filing sulla stessa base sono in disaccordo o il filing della riga si contraddice. Un numero ottenuto moltiplicando per un rapporto di riesposizione non è un fatto e non viene mai scritto.
- **Esercizio non provato** (catena interrotta o ambigua, periodo fuori tolleranza, esercizio della riga assente dal suo filing): la cella resta come R14 l'ha lasciata, con stato UNVERIFIABLE; è contata nella ricevuta e segnalata dal misuratore.
- Le celle vuote nella base non vengono riempite da questa clausola.
- Scala d'unità: non normalizzata. Un conteggio sotto 100.000 è marcato `UNIT_SCALE_SUSPECT` e resta aperto.

## R20 — ricavi con concetto coerente

- Ambito: 22 righe. In 17 i due estremi di `revenue_cagr3` hanno concetti diversi; in 5 il ricavo FY-3 è vuoto pur con periodo noto.
- Regola: entrambi gli estremi devono essere fatti diretti dello **stesso** concetto, quello di `annual_revenue`. Il valore annuale deve essere confermato nel filing della riga.
- `annual_revenue` non viene mai modificato. Le colonne dei tag non vengono riscritte: per le celle corrette fa fede il registro delle correzioni.
- Se nessuna coppia coerente è ricavabile dai payload verificati: `revenue_cagr3` diventa vuoto; il ricavo FY-3 memorizzato resta.
- Un ricavo FY-3 vuoto viene riempito solo da un fatto diretto che supera la clausola di calendario.
- Diagnostica, senza effetto sulle celle: se è disponibile il payload dell'altro concetto e il filing della riga riporta a FY0 un ricavo diverso, la riga è marcata e la scelta del concetto resta aperta sotto R20.

## Valori scritti

Ogni sostituzione o riempimento deve essere esattamente il testo del valore del fatto diretto citato nel registro delle correzioni. Il codice lo controlla a ogni scrittura e di nuovo prima di emettere la ricevuta.

## Derivati

Ricalcolati solo se un loro ingresso è cambiato, con le formule congelate R10B (`cagr3`, `fcf`, `per_share`). Ingresso mancante: derivato vuoto, mai zero. `share_change` segue `diluted_shares_yoy` solo se i due testi coincidevano nella base.

## Colonne modificabili

`annual_diluted_shares`, `prior_diluted_shares`, `fy_minus_1_diluted_shares`, `fy_minus_2_diluted_shares`, `fy_minus_3_diluted_shares`, `diluted_shares_yoy`, `share_change`, `fcf_per_share_cagr3`, `fy_minus_3_revenue`, `revenue_cagr3`. Ogni altra cella, e ogni riga fuori ambito, deve restare identica: il codice lo verifica due volte.

## Cosa resta aperto anche dopo questi contratti

- R13 per le righe non selezionate dallo screening, per le celle in ambito rimaste UNVERIFIABLE e per la scala d'unità (MCD).
- R20: la scelta fra ricavi da contratti e ricavi totali quando la società li espone entrambi.
- R15, R19, R21, R4/MET.
- La validazione economica di qualunque ranking.

## Decisioni che il contratto incorpora e che puoi cambiare

| Parametro | Valore proposto | Alternativa |
|---|---|---|
| Tolleranza di fine periodo | 7 giorni | 0 (nessuna), con perdita dei calendari a 52/53 settimane |
| Durata annuale | 350–378 giorni | più stretta: 357–378 |
| Tolleranza di base | 0,5% | 0,1%: più celle arrotondate verrebbero riscritte |
| Fonte FY-3 | un solo passaggio (filing che concorda con quello della riga) | catena di più filing: più copertura, più rischio |
| Periodo R14 | fine identica, inizio entro 7 giorni | inizio esatto: una differenza di un giorno svuoterebbe la cella |
| Esercizio non provato | cella lasciata e segnalata | svuotare anche in questo caso: più prudente, ma la resa sui dati reali è ignota |
| Ambito R13 | 33 righe da screening | tutte le 504: richiede 504 payload e riesame dell'impatto |
