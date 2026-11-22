# Investment OS V4.3 — Sviluppo 0.6: risposta al REQUEST_CHANGES della 0.5

Data: 2026-10-06 · Stato: SVILUPPO, IN ATTESA DI RIESAME, NON PROMOSSO · Nuova copia di sviluppo; i pacchetti 0.3 (accettato), 0.4, 0.4.1 e 0.5 non sono modificati

## COSA DEVI FARE

**NON FARE NULLA sul portafoglio. Acquisti bloccati (504/504).**

1. Porta questo ZIP nella chat del revisore con `MANDATO_RIESAME_0_6.txt` e lo SHA-256 che ti do in chat.
2. Se non hai ancora eseguito il workflow SEC: usa il drop-in di questa versione. Se lo hai già eseguito con quello della 0.5, l'artifact resta valido.
3. Non comporre in modalità VERIFIED prima dell'esito del riesame.

## 1. Esito recepito

REQUEST_CHANGES della revisione separata 0.5, limitato al compositore in modalità VERIFIED e alle clausole R13 e R14. Il revisore ha riprodotto tutto ciò che la 0.5 dichiarava. Lo SHA-256 da lui calcolato per lo ZIP 0.5 (`efbc4740…f134b3`) coincide con il mio.

Risposta punto per punto: `RISPOSTA_AL_REQUEST_CHANGES_0_5.md`.

## 2. Correzioni

| ID | Prima | Ora |
|---|---|---|
| M1 | VERIFIED riusciva con una ricevuta vuota o parziale | Rifiutata se la ricevuta non dichiara la lista di scarico fissata o se manca anche una sola delle 57 chiavi (scaricata o assente) |
| M2 | R14 svuotava la cella anche quando il filing della riga riportava il periodo | Il fatto del filing della riga sostituisce il valore memorizzato; si svuota solo se il filing non riporta il periodo, o lo riporta in modo contraddittorio o non positivo. Precedenza R14 → R13 scritta nel contratto |
| M3 | La cella si svuotava solo se il valore coincideva con un fatto riportato | Con esercizio provato e nessun fatto diretto utilizzabile si svuota sempre, e i derivati si ricalcolano |
| B1 | L'anteprima passava in VERIFIED cambiando una stringa | Il marcatore d'anteprima nei payload è rifiutato in VERIFIED e obbligatorio in PREVIEW |
| B2 | Cartella dei payload e `raw/` potevano essere symlink | Rifiutati |
| B3 | Payload malformati uscivano come traceback | `CORRECTION_BLOCKED`, uscita 1; errori imprevisti uscita 2, senza traceback e senza file |
| B4 | Un import senza `-B` lasciava bytecode | Ogni modulo rimuove il proprio bytecode; verificato su tutti i moduli |

Il contratto è cambiato, quindi ha un nuovo hash fissato nel codice. Le tre correzioni medie cambiano il comportamento solo in presenza di payload: l'uscita PENDING resta byte-identica al composto accettato.

### Sonde del revisore rieseguite sulla 0.6

| Sonda | Esito 0.5 | Esito 0.6 |
|---|---|---|
| M1, ricevuta senza payload | candidato, 0 celle | rifiutata, nessuna uscita |
| M2, CTAS | FY-1 e variazione annua svuotati | FY-1 = fatto del filing della riga; variazione ricalcolata |
| M3, NFLX | FY-3 e derivato invariati | FY-3 svuotato; derivato svuotato |
| B1, anteprima come SEC | 105 celle in VERIFIED | rifiutata dal marcatore |
| B2, symlink | accettati | rifiutati |
| B3, payload malformati | traceback | `CORRECTION_BLOCKED`, uscita 1 |
| B4, import senza `-B` | bytecode lasciato | nessun bytecode |

Log completo: `evidence/SONDE_REVISORE_SU_0_6.log`.

## 3. Contratto 0.6 in breve

- **Fonte**: solo payload SEC grezzi con hash. In VERIFIED: lista di scarico fissata e 57 chiavi complete.
- **Calendario**: invariato (form annuale, 350–378 giorni, esercizio provato per contiguità, fine entro 7 giorni).
- **R14**: vale il fatto del filing della riga.
- **Precedenza**: R14, poi R13 il cui verdetto è finale; se R13 non prova l'esercizio vale R14; le celle vuote nella base non si riempiono.
- **R13**: fatto diretto sulla base della riga, oppure cella svuotata; mai un valore inferito.
- **R20**: invariato, più una diagnostica sull'altro concetto di ricavo che non tocca le celle.
- **Scritture**: ogni valore scritto deve essere il testo del fatto citato; controllato due volte.

Ambiti invariati: 33 righe R13, 10 celle R14, 22 righe R20. Dieci colonne modificabili.

## 4. Stato dell'uscita

**PENDING, non è un candidato.** Hash `e7f23e87…d495a`, 0 celle cambiate, ranking e coda identici all'accettato, actionability 504/504 false. Le 57 chiavi risultano tutte mancanti, com'è corretto senza un run del workflow.

### Anteprima non verificata

Dal registro estratto da modello, 128 date d'inizio sintetiche; copre 39 chiavi su 57. Non prova nulla sulla SEC.

| Misura | 0.6 |
|---|---|
| Celle cambiate | 105 |
| R14 | 10/10 identiche nel filing della riga |
| R13 sostituite da fatto diretto | 55, in 27 titoli |
| R13 svuotate | 8: FAST, IBKR, LRCX, NFLX, NOW, ORLY, PANW, TPL |
| R13 con esercizio non provato | 1: CTAS FY-3 (catena incompleta nel registro) |
| R20 | CEG sostituito, TJX e BBY riempiti, KEYS invariato; 18 righe senza payload |
| R20, scelta del concetto aperta | CEG |
| IOS numerici | 213 (persi FAST, LRCX, NFLX, NOW, ORLY, PANW; acquisiti BBY, TJX) |
| Coda misurata | DECK FISV CMCSA FOX IBKR GM ADBE NEM FIX ANET |
| In coda con ingressi non verificati | CMCSA |

I numeri coincidono con l'anteprima 0.5: nel registro estratto da modello i casi M2 e M3 non si presentano. Le correzioni contano sui payload reali.

La coda misurata non è utilizzabile per acquisti. I nomi che vi compaiono non sono idee d'investimento.

## 5. Workflow

- Tre esiti distinti del confronto: tutto confermato; righe non confermate (run verde con avviso: è un risultato); errore tecnico (run rosso: non esiste un risultato).
- Un 404 diventa assenza solo dopo due risposte 404; le chiavi assenti compaiono nel riepilogo.
- Hash di `VERIFICATION.csv` nel riepilogo e nell'artifact; commit e numero del run nel riepilogo.
- `.gitattributes` nella cartella del drop-in contro la conversione dei fine riga.
- Lista di scarico byte-identica alla 0.5 (185 chiavi).

**Non eseguito.** La logica del passo di confronto è stata simulata in shell con codici 0, 1 e 2; scarico e confronto sono provati con rete simulata.

## 6. Verifiche eseguite

| Verifica | Risultato |
|---|---|
| Hash ZIP 0.3 | `6827a7e4…551f0e`, identico |
| Albero del pacchetto accettato a fine lavoro | identico allo ZIP, nessun bytecode |
| Test contratti | 89/89, anche con Python ottimizzato |
| Test strumenti | 28/28, anche con Python ottimizzato |
| Test misuratore | 3/3, anche con Python ottimizzato |
| Mutazioni scritte a mano | 119 mutanti, 118 rilevati |
| Sonde del revisore | 7/7 con l'esito richiesto |
| Uscita PENDING | byte-identica al composto accettato |
| Ranking e coda accettati | riprodotti byte per byte |
| Lista di scarico rigenerata | byte-identica |
| Riconciliazione MET | invariata rispetto alla 0.5, chiude sulle celle |

Mutante sopravvissuto: C16, l'invariante finale sulle colonne, ridondante con la guardia per cella (il revisore la considera accettabile). Copertura: 66 dei 118 mutanti rilevati sono fermati da un solo test. È migliorata poco rispetto alla 0.5 (49 su 70) e resta sottile.

## 7. Non eseguito

- Workflow GitHub e scarico SEC reale.
- Modalità VERIFIED su payload veri.
- Riesame di questa versione.
- Azioni GitHub fissate per commit.
- S2/S3/S4, Blind Test, qualunque validazione economica.

## 8. Decisioni necessarie

| # | Punto | Scelta nel contratto 0.6 | Alternativa |
|---|---|---|---|
| D1 | Cella in ambito con esercizio non provato | lasciata, contata e segnalata | svuotarla: più prudente, resa sui dati reali ignota |
| D2 | Periodo in R14 | fine identica, inizio entro 7 giorni | inizio esatto |
| D3 | Concetto R20 | quello dell'estremo annuale; riga marcata se l'altro concetto dà un FY0 diverso | ricavi totali quando disponibili |
| D4 | Ambito R13 | 33 righe da screening | tutte le 504 |
| D5 | Scala d'unità (MCD) | solo segnalata | normalizzazione con contratto dedicato |
| D6 | Azioni del workflow | per tag | per commit, da fissare tu nel repository |
| D7 | Concetto assente alla SEC | R14 svuota, R20 ritira la crescita, R13 lascia e segnala | trattarlo come errore e bloccare |

## 9. Residui

Nessun residuo chiuso. R13, R14, R15, R19, R20, R21 e riserva R4/MET aperti. Dettaglio in `RESIDUI_AGGIORNATI_0_6.json`.

## 10. Stato

V4.2 preservata · composto e pacchetti accettati preservati · nessuna promozione, freeze, R11/R12, LIVE · acquisti bloccati · progetto non al 100%.
