# V4.3 — Fase dei dati reali con il drop-in 0.6: istruzioni passo passo

Stato al 2026-10-07: **il workflow NON è stato eseguito.** Da questa sessione GitHub non è operabile
(credenziale `gh` non valida, repository non noto, uscita diretta verso data.sec.gov bloccata).
Non esiste alcuna composizione VERIFIED su dati reali. Acquisti bloccati 504/504. Nessuna promozione.

## A. Caricare i 7 file (cartella `1_CARICARE_SU_GITHUB`)

Destinazione: radice del ramo predefinito del repository, stessi percorsi.

```
.github/workflows/v43_sec_payload_verify.yml
v43_sec_verify/.gitattributes
v43_sec_verify/PINS.sha256
v43_sec_verify/SEC_FACTS_LEDGER.csv
v43_sec_verify/SEC_FETCH_LIST.csv
v43_sec_verify/facts.py
v43_sec_verify/sec_payloads.py
```

1. Caricare i file **così come sono**, senza aprirli e risalvarli. Nessuna conversione dei fine riga:
   `SEC_FETCH_LIST.csv` è in CRLF e deve restare tale. La via più sicura è "Add file → Upload files"
   dal sito, trascinando le due cartelle; `.gitattributes` (`* -text`) va caricato nello stesso commit.
   Da riga di comando: `git config core.autocrlf false` prima di `git add`.
2. Controllo facoltativo prima del commit: `sha256sum` dei 7 file contro `SHA256_DEI_FILE_DA_CARICARE.txt`.
   Se un hash differisce, il primo passo del workflow si ferma (run rosso): è il comportamento voluto.
3. Presupposti nel repository, che il workflow verifica da solo:
   - esiste `data/v4_2/r10b/36268043494/V4_2_R10B_RECOVERY_PROVENANCE.csv` con SHA-256
     `1eb6937ff390a9dad591f87d816c01e56333e99a8e4c93ab3e66707862bad224`;
   - esiste il secret `SEC_CONTACT_EMAIL` (Settings → Secrets and variables → Actions). Il valore non va
     scritto in nessun file né in chat.
4. Il caricamento non tocca V4.2, `data/current` né file congelati: aggiunge solo i 7 file.

## B. Eseguire

1. Actions → **V4.3 SEC payload verification (read-only)** → Run workflow → ramo predefinito.
2. Il workflow ha `contents: read`, non fa commit né push; l'unica uscita è l'artifact.
3. Esiti:

| Run | Riepilogo | Significato |
|---|---|---|
| verde | `ALL_ROWS_CONFIRMED` | tutte le righe di registro e provenienza confermate |
| verde con avviso | `ROWS_NOT_CONFIRMED` | è un risultato: alcune righe non confermate, vedi `VERIFICATION.csv` |
| rosso | `TECHNICAL_ERROR` / `NOT_RUN…` / `NOT_PRODUCED` | **nessun risultato**. Non usare l'artifact per comporre |

   Un rifiuto 403 della SEC verso i runner GitHub è un errore tecnico (run rosso), non un'assenza di dati.
   In quel caso riferire il messaggio; non ripetere più volte in sequenza.

## C. Annotare dal RIEPILOGO del run (non dall'artifact)

- `PAYLOAD_RECEIPT_SHA256`
- `Commit` (40 caratteri)
- `run` (numero)
- `Comparison outcome`
- riga `Fetch`: `absent_keys`

## D. Conservare l'artifact

1. Scaricare `v43-sec-payloads-<run>` (ZIP). Non aprirlo e risalvarlo; conservare lo ZIP originale.
2. Annotarne lo SHA-256 (`sha256sum` / `Get-FileHash`). Scadenza su GitHub: 90 giorni — tenerne copia fuori.
3. Riportare in chat: lo ZIP dell'artifact, i tre valori del punto C, l'esito, lo SHA-256 dello ZIP.

## E. Dopo lo scarico (cartella `2_DOPO_LO_SCARICO`)

Lo faccio io appena ricevo artifact e valori; il comando è riproducibile anche fuori da questa sessione:

```
python -I -B fase_verified.py --dev06 <0.6 estratto> --accepted03 <COPIA dello 0.3 estratto> \
  --artifact <artifact estratto> --receipt-sha256 <C1> --github-sha <C2> --run-id <C3> --out <cartella nuova>
```

Usa compositore e misuratore del pacchetto 0.6 accettato senza modificarli. Si ferma (`FASE_FERMATA`, uscita 1,
nessuna uscita scritta) se ricevuta, commit, run, origine `SEC_HTTPS`, lista di scarico o le 185 chiavi non
corrispondono. Produce composizione VERIFIED (`CANDIDATE_0_6_NOT_PROMOTED.csv`), misura, relazione e ZIP per
la revisione separata, con:

- `required_keys_absent_at_sec` e l'elenco delle chiavi assenti;
- `in_scope_cells_left_unverifiable` e l'elenco delle celle;
- `measured_with_unverified_inputs` e l'elenco dei titoli (da trattare come **non corretti**);
- **O1**: ogni sostituzione R14, una riga ciascuna, con valore prima/dopo, rapporto, e segnali
  (valore < 100 000, rapporto potenza di dieci, rapporto fuori 0,75–1,33, riga che entra o esce dallo
  screening dopo la composizione, riga fuori dall'ambito R13);
- **O2**: ogni scrittura R13 con valore zero o negativo.

`PROVA_A_SECCO_SINTETICA_NON_E_UN_RISULTATO.log` è una prova dello strumento su payload **inventati**
(divisione WMT, caso FOX in milioni, caso MPC a zero). Non contiene alcun dato reale e non è un risultato.

## F. Lettura già concordata con il revisore

- Molte chiavi assenti ⇒ run da leggere come fallito nella sostanza.
- Nessuna azione di portafoglio da composizione o misura. Residui R13, R14, R15, R19, R20, R21 e riserva
  R4/MET restano aperti. Nessun freeze, R11/R12, LIVE, BUY/ADD o validazione dei rendimenti.
