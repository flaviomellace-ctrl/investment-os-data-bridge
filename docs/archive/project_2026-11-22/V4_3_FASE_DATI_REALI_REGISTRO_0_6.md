# V4.3 — Sviluppo 0.6: ACCEPT_FOR_NEXT_DEVELOPMENT_STAGE, condizioni e osservazioni O1–O4

| Campo | Valore |
|---|---|
| Data di registrazione | 2026-10-07 |
| Esito | ACCEPT_FOR_NEXT_DEVELOPMENT_STAGE |
| Ambito | compositore, contratto R13/R14/R20 v0.6, misuratore, verificatore del manifest, testo del workflow |
| ZIP 0.6 | SHA-256 `9214b7b6bf8d34f1cad5d6c15325c4a8a3d563b0c3ff824a41902ac6b4c58458` |
| Hash del contratto | `029339b8d595d103e6863eb50c14dc4a05e78ac4c83dfe4cc72cc82276074d16` |
| Natura | revisione di un'IA in chat separata; non R11/R12; nessuna promozione, freeze, LIVE, BUY/ADD, validazione dei rendimenti |
| Fuori ambito | qualunque dato reale: nessuno scarico SEC è stato esaminato |

## Condizioni del revisore

| # | Condizione | Stato al 2026-10-07 |
|---|---|---|
| 1 | Eseguire il workflow con il drop-in 0.6 caricato senza conversione dei fine riga; annotare `PAYLOAD_RECEIPT_SHA256`, commit e numero del run dal riepilogo | **NON ESEGUITO** — GitHub non operabile da questa sessione; file e istruzioni consegnati |
| 2 | Comporre in VERIFIED e misurare; nessuna azione di portafoglio | IN ATTESA dell'artifact; strumento pronto e provato solo su dati sintetici |
| 3 | Portare a revisione separata: artifact, cartella di composizione, misura e i conteggi `required_keys_absent_at_sec`, `in_scope_cells_left_unverifiable`, `measured_with_unverified_inputs` | IN ATTESA |
| 4 | Alla revisione leggere a mano ogni riga R14 REPLACE (O1) e ogni scrittura R13 con valore non positivo (O2) | la relazione di fase le elenca una per una; IN ATTESA dei dati |
| 5 | Correggere O1–O4 nella prossima versione di sviluppo; O1 prima di dare peso a un candidato in cui R14 ha sostituito qualcosa | APERTO, registrato sotto |

Lettura concordata: un run con molte assenze è fallito nella sostanza; i titoli in
`measured_with_unverified_inputs` vanno trattati come non corretti.

## Osservazioni da correggere nella prossima versione (riprodotte sulla 0.6 accettata)

| Id | Gravità | Fatto | Correzione prevista |
|---|---|---|---|
| O1 | medio-bassa | R14 REPLACE non ha un segnale di scala dell'unità né un controllo di coerenza della riga; un fatto annuale in milioni viene scritto (caso FOX: variazione −99,9999%) e la riga non viene riesaminata dallo screening | stato `UNIT_SCALE_SUSPECT` su R14; riesecuzione dello screening dopo la composizione |
| O2 | bassa | R13 scrive un fatto diretto pari a zero o negativo | svuotare la cella con stato dedicato |
| O3 | bassa | una PREVIEW è misurabile come VERIFIED modificando due campi della ricevuta | controllare nome del file contro la modalità e `payload_origin == SEC_HTTPS` |
| O4 | minima | `tests/*.py` importati senza `-B` lasciano bytecode | disattivare il bytecode nei moduli di test |

Finché O1 non è corretta nel codice, il presidio è nella relazione di fase: ogni sostituzione R14 è
esposta con valore prima/dopo e segnali di scala, e nessun peso va dato a un candidato in cui R14 ha sostituito.

## Invariati

V4.2, pacchetti accettati (0.3 `6827a7e4…1f0e`, 0.6 `9214b7b6…8458`), motore congelato, `data/current`.
Residui R13, R14, R15, R19, R20, R21 e riserva R4/MET aperti. Acquisti bloccati 504/504.
