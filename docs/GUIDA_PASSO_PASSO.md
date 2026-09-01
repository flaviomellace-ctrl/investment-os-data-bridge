# Investment OS Data Bridge — guida passo passo

Questa guida è pensata per non richiedere programmazione.

## Risultato finale

Una volta configurato, non dovrai più scaricare a mano State Street o i grandi ZIP SEC. GitHub Actions aggiornerà i dati automaticamente e Claude leggerà file piccoli già preparati.

---

## PASSO 1 — Crea il repository GitHub

1. Vai su GitHub e accedi.
2. Premi **New repository**.
3. Nome consigliato: `investment-os-data-bridge`.
4. Puoi scegliere **Public**: il repository deve contenere soltanto dati pubblici e codice, quindi è la configurazione più semplice per Claude. Se preferisci Private, è possibile, ma Claude dovrà avere accesso GitHub autenticato.
5. **NON** aggiungere README, `.gitignore` o licenza dalla schermata GitHub: sono già presenti nello ZIP.
6. Premi **Create repository**.

---

## PASSO 2 — Carica i file dello ZIP

Metodo semplice dal browser:

1. Nel repository vuoto scegli **uploading an existing file** / **Add file → Upload files**.
2. Trascina **il contenuto della cartella `Investment_OS_Data_Bridge`**, non la cartella ZIP stessa.
3. Assicurati che vengano caricati anche `.github/workflows/update-data.yml` e `.github/workflows/smoke-test.yml`.
4. Commit message: `Initial Investment OS Data Bridge`.
5. Premi **Commit changes**.

Se il browser non conserva correttamente le cartelle nascoste `.github`, usa GitHub Desktop oppure dimmelo: ti guiderò nel metodo alternativo.

---

## PASSO 3 — Crea il secret SEC_CONTACT_EMAIL

La SEC chiede che gli strumenti automatici dichiarino il proprio User-Agent con un contatto. Il bridge resta molto sotto il limite SEC di 10 richieste al secondo.

1. Nel repository GitHub apri **Settings**.
2. Nel menu sinistro: **Secrets and variables → Actions**.
3. Scheda **Secrets**.
4. Premi **New repository secret**.
5. Name:

`SEC_CONTACT_EMAIL`

6. Value: inserisci un tuo indirizzo email valido.
7. Premi **Add secret**.

L'email viene utilizzata nel solo header HTTP inviato alla SEC. Il codice non la scrive nei CSV, nel manifest o nei commit.

---

## PASSO 4 — Avvia il primo aggiornamento

1. Apri la scheda **Actions** del repository.
2. A sinistra scegli **Update Investment OS Data Bridge**.
3. Premi **Run workflow**.
4. Lascia `Forza il rebuild dei fondamentali SEC` su **false**: al primo avvio i fondamentali non esistono e quindi verranno costruiti automaticamente.
5. Premi **Run workflow**.
6. Attendi che il pallino diventi verde.

Il primo run è il più pesante perché deve scaricare e leggere gli ultimi 4 trimestri SEC. I run settimanali successivi sono molto più leggeri; il bulk viene ricostruito solo quando la SEC pubblica un nuovo trimestre.

---

## PASSO 5 — Controlla l'esito

Dopo il run verde apri:

`data/current/status.md`

poi:

`data/current/manifest.json`

Controlla in particolare:

- numero righe dell'universo;
- percentuale ticker con CIK SEC;
- ultimo trimestre SEC disponibile;
- percentuale di filing annuali individuati;
- percentuale di core metric coverage.

Il bridge non deve fingere una copertura che non possiede.

---

## PASSO 6 — Come si aggiorna in futuro

Non devi fare nulla.

Il workflow parte automaticamente **ogni lunedì alle 05:17 UTC**.

Fa due cose diverse:

- aggiorna l'universo State Street ogni settimana;
- controlla la SEC e ricostruisce i fondamentali soltanto quando compare un nuovo trimestre.

Puoi sempre avviarlo manualmente da **Actions → Update Investment OS Data Bridge → Run workflow**.

Usa `force_sec=true` soltanto se vuoi ricostruire da zero i fondamentali anche senza un nuovo trimestre SEC.

---

## PASSO 7 — Collegalo a Claude Investment OS

Dopo il primo run, apri:

`data/current/claude_sources.md`

GitHub Actions avrà scritto automaticamente i link `raw.githubusercontent.com` del tuo repository.

Nel Project Claude incolla poi il contenuto di:

`docs/PROMPT_CLAUDE_V3_DOPO_SETUP.txt`

Prima di avviare il V3, Claude deve leggere almeno:

- `manifest.json`
- `status.md`
- `sp500_universe.csv`
- `sp500_fundamentals.csv`
- `sp500_coverage.csv`

Non aprire ancora il materiale di validazione.

---

## PASSO 8 — Cosa NON mettere nel repository

Mai caricare:

- API key FMP;
- password;
- credenziali Google;
- patrimonio/capitale investibile;
- Investor Policy Statement personale;
- ledger personali;
- file della validazione cieca;
- email o documenti privati.

Il Data Bridge deve rimanere un'infrastruttura di **soli dati pubblici**.

---

## PASSO 9 — Se un workflow diventa rosso

Non modificare immediatamente il sistema di investimento.

Apri il run rosso in GitHub Actions e copia l'errore. Le cause più probabili sono:

1. State Street ha cambiato il formato o URL dell'Excel;
2. la SEC ha modificato una pagina/file;
3. `SEC_CONTACT_EMAIL` non è configurato;
4. timeout temporaneo del sito sorgente;
5. modifica delle colonne SEC.

In quel caso fai correggere il Data Bridge; non sostituire dati mancanti con zero e non fare ranking su dati incompleti.

---

## PASSO 10 — Controllo metodologico

Il Data Bridge è uno strato di raccolta/normalizzazione, non un investment model.

Quindi:

**Data Bridge → screening → BQS → IOS → deep dive → Decision Gate → eventuale decisione.**

Per una decisione reale, il bulk SEC non sostituisce l'ultimo 10-K/10-Q/8-K o le Investor Relations. Il dataset SEC trimestrale serve soprattutto per la discovery ampia e comparabile.
