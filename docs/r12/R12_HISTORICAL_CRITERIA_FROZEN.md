# R12 — Validazione storica point-in-time. Criteri congelati

Congelati il 14 novembre 2026, prima che l'esecutore indipendente esegua la pipeline sui casi storici
e prima di qualunque calcolo dei rendimenti successivi. Scelte nuove di questa data, approvate nell'impianto
generale (D1–D5, B1) dall'utente; nessuna preregistrazione storica viene rivendicata.

## Oggetto
Pipeline integrata V4.2 congelata, versione 1.1 (hash nel manifest R12), eseguita sui candidati ricostruiti
alla data del 14/11/2023 e del 14/11/2024: universo S&P 500 ricostruito alla data, fondamentali SEC depositati
entro la data, prezzi alla data, capitalizzazione secondo B1. Nessuna evidenza documentale per le singole
imprese: il test misura lo strato quantitativo (selezione della coda 7+3 e gate), non il Decision Gate umano.

## Misura degli esiti (dopo il congelamento dell'output dell'esecutore)
Rendimento totale in dollari, prezzi rettificati per dividendi e operazioni sul capitale, dalla data di
osservazione a 24 mesi dopo (14/11/2025 e 13/11/2026 o ultimo giorno di borsa precedente). Titoli usciti dal
listino: ultimo prezzo disponibile, segnalati. Universo di confronto: membri alla data con prezzo disponibile.

## Criteri
- C1 CRITICO, integrità temporale: nessun deposito SEC con data successiva alla data di osservazione e nessun prezzo
  successivo negli input; output deterministico; nessuna eccezione; buy_add_allowed falso su ogni riga.
- C2 CRITICO, funzionamento: IOS calcolabile su almeno il 25% delle righe per ciascuna data (sui dati correnti
  DATA34 è il 40%; sotto il 25% la pipeline non sta valutando l'universo ma un residuo).
- M1 MAGGIORE, perdite permanenti: la quota di titoli in coda (20 posizioni, due date) con rendimento a 24 mesi
  pari o inferiore a −50% non supera la quota dell'universo.
- M2 MAGGIORE, nessuna selezione avversa: la mediana dei rendimenti a 24 mesi della coda non è inferiore di oltre
  10 punti percentuali alla mediana dell'universo (dati delle due date aggregati).
- Soglie: 100% CRITICI e 100% MAGGIORI (decisione D2).

## Informativi, non decisivi
Mediana Lane V e Lane I separate; mediana del decile IOS più alto; correlazione di rango IOS–rendimento;
confronto con l'indice.

## Motivazione e limite dichiarato
Con 20 osservazioni nessun test statistico può dimostrare una capacità di battere il mercato: R12 storico è
costruito per bocciare un sistema che usa informazioni future, non funziona, o seleziona sistematicamente
titoli peggiori della media. La prova di capacità resta alla validazione forward a 1, 3 e 5 anni.
Limiti: universo ricostruito da elenco pubblico delle modifiche (possibili omissioni); capitalizzazione per
deroga B1 (prezzo × azioni in copertina del 10-K); titoli delistati senza prezzo esclusi e segnalati.
