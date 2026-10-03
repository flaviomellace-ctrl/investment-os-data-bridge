# V4.2 R10L — correzione della revisione D&A FIX

3 ottobre 2026. Sistema **NOT LIVE**. Motore, ranking e regole economiche congelati invariati.

## Errore corretto

La revisione R10F aveva segnalato 79,578 milioni USD in Companyfacts contro 79,580 milioni nel filing, ipotizzando un conflitto di 2.000 USD. Questo era un **errore della revisione**, non una discrepanza dimostrata delle fonti.

La Companyfacts sigillata R10E e il dossier FIX originario riportano entrambi 79.580.000 USD per `AmortizationOfIntangibleAssets`, accession `0001104659-26-017530`, periodo 1 gennaio–31 dicembre 2025, FY/10-K. La voce nel rendiconto primario coincide. Depreciation 62.379.000 + amortization 79.580.000 = D&A 141.959.000 USD. Differenza fra le fonti: **zero**.

La correzione è esplicita e append-only: R10F, R10I, R10K e il supplemento R10E–K restano documenti storici; la loro affermazione sul conflitto FIX è superseded da R10L. Le vecchie ricevute provano i controlli che effettivamente eseguivano: non verificavano il valore Companyfacts narrato nel motivo R10F.

## Verifica riproducibile

Il registro R10L verifica il D&A con ID dei fatti, attributi, contesto annuale e hash del filing tramite il verificatore R10F invariato. Il controllo aggiuntivo verifica l'hash completo Companyfacts, seleziona un solo record per accession/periodo/form/fp e confronta l'importo con il componente primario. Una diversa accession, un dato trimestrale o un semplice match sul tag non bastano.

Lo zero è una **differenza verificata fra due valori presenti**, non la sostituzione di MISSING con zero.

## Decisione e limiti

Il subproblema «conflitto D&A di 2.000 USD» è chiuso come errore di revisione. Il D&A documentato rimane 141.959.000 USD; nessun input congelato viene aggiornato automaticamente e nessun ranking viene ricalcolato.

Il dossier economico FIX resta aperto: qualità del capitale circolante, anticipi e costi di commessa, surety/garanzie e completezza del perimetro richiedono ancora decisioni documentate. Normalized OE non viene dichiarato completo. Nessun BUY/ADD, nessun PASS R11/R12 e nessuna operatività derivano da questa correzione.

Il supplemento anticipato per Claude non è la consegna finale. R10L deve essere incluso e il riferimento al conflitto FIX rimosso dal prossimo pacchetto finale, conservando la storia della correzione.
