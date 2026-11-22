# Pre-controllo filtro di qualità anti-"trappola del valore" — 22/11/2026

Richiesta di Flavio (22/11/2026, 21:16): "trova un modo per superare R12... voglio davvero un sistema sicuro".
Ipotesi: un filtro di qualità di tipo Piotroski (pubblicato in letteratura) toglie dalla coda i titoli poi crollati.
Controllo informativo sulle 10 date già usate (2014-2024). Le date 2010-2013 NON sono state toccate.

## Metodo
Per ognuna delle 98 posizioni in coda con esito a 24 mesi (versione 1.1, file pit_candidate.csv di ogni data) si
contano 7 segnali calcolabili con i dati point-in-time già presenti: utile netto > 0; flusso di cassa operativo > 0;
utile in crescita; cassa operativa > utile; azioni diluite non in aumento; margine operativo in crescita; ricavi in
crescita. Piotroski completo (leva, liquidità corrente, rotazione dell'attivo, margine lordo) e Altman Z richiedono
voci di bilancio non estratte (attivo/passivo corrente, utili non distribuiti, margine lordo, attivo dell'anno prima).

## Risultato
| Gruppo | Posizioni | Punteggio medio (0-7) |
|---|---|---|
| Crollate (≤ −50% a 24 mesi) | 7 | 5,86 |
| Tutte le altre | 91 | 5,59 |

Filtro "punteggio ≥ 5": tiene 76 posizioni con 6 crolli (7,9%); scarta 22 posizioni con 1 crollo (4,5%).
Il filtro peggiora il rischio invece di ridurlo. I crolli (Fossil 2015, Signet 2017, Alliance Data 2017 e 2018,
Lululemon 2024, Deckers 2024, Builders FirstSource 2024) avevano conti in salute al momento della scelta:
il deterioramento è arrivato dopo. Inferenza: anche Piotroski completo e Altman Z li avrebbero tenuti (bilanci
con poco debito e margini alti), quindi un filtro di solidità non intercetta questo tipo di errore.

## Decisione
Nessuna regola congelata. Date 2010-2013 non consumate. R12 resta NON SUPERATO.
Una regola costruita guardando quali titoli sono crollati nelle 10 date note (settore, margini al massimo storico)
sarebbe adattata ai dati (overfitting) e non renderebbe il sistema più sicuro.
