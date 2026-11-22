# Criteri R12 v2 (M1 statistico) e test R12-quater — congelati il 22/11/2026 prima di qualunque dato delle nuove date

## Approvazione
Flavio Mellace ha approvato in chat il 22/11/2026 la proposta: "Approvo, test 2014-2017". Modifica richiesta dalla
Costituzione par. 0: proposta esplicita, motivazione, approvazione umana, nuova versione, hash, changelog.

## Motivazione
M1 v1 ("quota di crolli in coda non superiore a quella dell'universo") con 20 titoli fallisce appena c'è un crollo
quando l'universo ne ha il 3%: una scelta casuale lo supera solo nel 54% dei casi. Il criterio non distingue
abilità da caso. R12 storico, R12-bis e R12-ter restano registrati come NON SUPERATI con M1 v1; nulla viene riscritto.

## Criteri v2 (tutti obbligatori)
- C1 invariato: nessun deposito o prezzo successivo alla data; esecuzione deterministica; nessun buy_add_allowed.
- C2 invariato: IOS calcolabile su almeno il 25% delle righe, per ciascuna data.
- M1 v2: siano n i titoli in coda con rendimento a 24 mesi su tutte le date del test e k quelli con rendimento ≤ −50%.
  Ipotesi nulla: ogni titolo in coda della data d crolla con probabilità p_d = quota di crolli dell'universo di d
  (distribuzione di Poisson-binomiale). p = P(X ≥ k). SUPERATO se p ≥ 0,05. Requisito: almeno 40 posizioni in coda.
  Titolo in coda senza rendimento: si verifica il motivo; fallimento o cancellazione per insolvenza = crollo;
  acquisizione o fusione = escluso; motivo non verificabile = crollo (prudenza).
- M2 invariato: mediana dei rendimenti della coda non più di 10 punti sotto la mediana dell'universo (tutte le date).

## Oggetto del test (nessun grado di libertà)
Pipeline V4.2-INTEGRATED-1.1 (sha 3eb0138c…), motore cbdb4e24…, BRIDGE-2 con gli hash di
`docs/r12/R12TER_BRIDGE2_SHA256SUMS`. Nessuna regola nuova, nessuna soglia diversa.

## Date (mai usate nel progetto)
14/11/2014, 16/11/2015 (il 15 era domenica), 15/11/2016, 15/11/2017. Rendimenti a 24 mesi (adjclose) all'ultima
seduta ≤ 14/11/2016, 16/11/2017, 15/11/2018, 15/11/2019.
Nota: i prezzi del 15/11/2018 e 15/11/2019 sono già stati letti per R12-ter; sistema e criteri sono congelati, quindi
quell'informazione non può influenzare la selezione.

## Procedura
Identica a R12-ter: universo dalla revisione Wikipedia alla data, SEC FSDS + companyfacts (stesso accession number)
depositati entro la data, prezzi Yahoo alla data letti dal browser con hash, replay in CI, esecutore indipendente,
rendimenti letti solo dopo il congelamento dell'output dell'esecutore.

## Regola di decisione
Tutti i criteri superati → R12 SUPERATO (criteri v2). Il passaggio a LIVE resta una decisione separata di Flavio.
Altrimenti → NON SUPERATO, registrato; nessun nuovo tentativo sulle stesse date.
