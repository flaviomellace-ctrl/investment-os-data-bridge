# Regola candidata 1.3 e test R12-quinto — congelati il 22/11/2026, prima di qualunque dato 2010-2013

## Regola 1.3 (shadow, non adottata)
Codice: `src/v12/v42_pipeline_v13_guard.py` (hash in fondo). Pipeline 1.1 congelata + BRIDGE-2 + guardia sull'ingresso
nella coda di approfondimento; BQS, IOS, soglie, corsie e Decision Gate invariati.
- G1 utile operativo ultimo anno < 90% dell'anno prima: escluso (entrambe le corsie).
- G2 ricavi ultimo anno < 97% dell'anno prima: escluso (entrambe le corsie).
- G3 solo corsia inflessione: crescita dei ricavi che si dimezza dopo un anno sopra il 10%: escluso; dati mancanti: escluso.
- G4 solo corsia valore (NUOVA): utile operativo ultimo anno inferiore a quello di tre anni prima: escluso.
  Dati mancanti: non escluso.
Motivazione: Costituzione par. 2 ("distingui volatilità da deterioramento economico") e par. 7 (Temporary Mispricing
richiede franchise intatta). R12-quater ha mostrato crolli in coda significativamente più frequenti del caso (p = 0,041)
su titoli a basso multiplo con utili in calo.
Limite dichiarato: la regola è scritta conoscendo i fallimenti 2014-2024. Per questo conta solo il test sulle date nuove.

## Test decisivo R12-quinto
Date mai usate: 15/11/2010, 15/11/2011, 15/11/2012, 15/11/2013 (giorni di borsa). Rendimenti a 24 mesi (adjclose)
all'ultima seduta ≤ 15/11/2012, 15/11/2013, 14/11/2014 (il 15 era sabato), 13/11/2015 (il 15 era domenica).
Criteri: R12 v2 approvati da Flavio (C1, C2 ≥ 25% per data, M1 v2 test di Poisson-binomiale con p ≥ 0,05 su almeno
40 posizioni, M2 ≥ universo − 10 punti), applicati alla coda della regola 1.3. Stessa regola per i titoli senza
rendimento. Procedura identica a R12-quater. Anche la coda 1.1 viene calcolata, ma solo come confronto informativo.

## Decisione
1.3 supera tutti i criteri → proposta di adozione a Flavio (nuova versione, hash, changelog). R12 si considera
superato solo per la versione 1.3 e solo dopo la sua approvazione.
1.3 fallisce → registrato; nessun nuovo tentativo sulle stesse date.
Informativo, dichiarato in-sample: effetto della 1.3 sulle 10 date già usate.
87b7483af18ca54ebea3d73e23ee3051052a6785d6bd8f94ebde87335a886843  src/v12/v42_pipeline_v13_guard.py
