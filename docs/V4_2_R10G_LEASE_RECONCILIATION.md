# V4.2 R10G — riconciliazione leasing

28 settembre 2026. **NOT LIVE**. Revisione documentale dei dieci candidati della coda congelata, sul medesimo accession dei loro dati fondamentali.

## Risultati verificabili

Il verificatore R10F, invariato, controlla 45 elementi contro gli HTML integrali archiviati da R10E: hash, fatto XBRL, attributi, valuta, periodo, dimensioni e aritmetica. Gli elementi comprendono importi e riconciliazioni della stessa categoria: **non sono 45 casi chiusi** e non vanno sommati tra loro.

Importi in **milioni di USD**. Le colonne rappresentano basi diverse della stessa obbligazione, non esposizioni additive.

| Società | Passività leasing operativi | Pagamenti futuri non attualizzati | Sconto implicito | Osservazione |
|---|---:|---:|---:|---|
| FISV | 763 | 904 | 141 | 126 correnti + 637 non correnti |
| CMCSA | 6.097 | 9.646 | 3.549 | Il totale dichiarato differisce di 1 dalla somma 686 + 5.410 = 6.096 |
| FOX | 863 | 1.349 | 486 | 41 + 822; periodo 30 giugno 2025 |
| GM | 1.301 | 1.548 | 248 | 266 + 1.035; pagamenti meno sconto danno 1.300, differenza conservata |
| ADBE | 438 | 485 | 47 | 77 + 361; periodo 28 novembre 2025 |
| TROW | 447,2 | 564 | 116,8 | Totale dichiarato |
| AMP | 276 | 302 | 26 | Totale dichiarato |
| NEM | 109 | 123 | 14 | Totale dichiarato |
| FIX | 338,132 | 485,830 | 147,698 | 35,542 correnti + 302,590 non correnti |
| ANET | MISSING | 90,5 | MISSING | Pagamenti al netto di sublocazioni dichiarate non materiali; non sono la passività attualizzata |

Le differenze CMCSA e GM sono compatibili con arrotondamenti dei prospetti pubblicati in milioni, ma la causa non è attestata dal verificatore: vengono registrate come `DISCLOSED_TOTAL_DIFFERENCE_RETAINED`, senza tolleranza aggiunta al codice e senza imporre un pareggio artificiale.

## Correzione documentata di completezza

Per FIX, il campo `operating_lease_liabilities` nell'export congelato dei candidati è 302.590.000 USD e la provenienza contiene soltanto `OperatingLeaseLiabilityNoncurrent`. Il totale riportato nel filing è 338.132.000 USD: manca la componente corrente di 35.542.000 USD. La somma delle due componenti coincide con il totale e con i pagamenti meno sconto.

La fonte per ADBE conferma 438 milioni e per TROW 447,2 milioni, già presenti nell'export. Si documentano inoltre passività operative per FISV, CMCSA, FOX, GM, AMP e NEM che nell'export risultavano MISSING. Per ANET non si sostituisce il valore dei pagamenti alla passività contabile.

L'export è usato per identificare il difetto, non per attestare nuovamente il suo hash canonico. La verifica riproducibile R10G riguarda esclusivamente le fonti primarie archiviate e il registro di revisione.

## Separazione dei perimetri

Tre ulteriori fatti sono registrati separatamente: leasing finanziari FISV 1.125 milioni, NEM 474 milioni, AMP zero esplicitamente rappresentato dal fatto XBRL. Lo zero di AMP non significa assenza di altre obbligazioni. Questi importi non vengono aggiunti al debito: occorre prima verificare se siano già inclusi nella metrica congelata.

I leasing operativi e i relativi pagamenti non possono essere sommati; lo sconto è una riconciliazione, non un nuovo impegno. Il dato di FOX usa il filing fondamentale 2025, non quello 2026 interrogato nell'overlay iniziale: non si mescolano i due periodi.

## Stato e lavoro residuo

R10F è stato riprodotto con successo su GitHub nel run **36380264085**, commit **9b712e79ea95a928f3f1529961357101ebed35d5**: 13 elementi e 8 test superati, ricevuta identica a quella locale.

R10G aggiunge un registro di evidenze e un controllo automatico in sola lettura. Nessuna modifica a V4.1, BQS, IOS, formule, classificatore, ranking o coda. Nessuna promozione automatica dei nuovi importi agli input congelati.

Restano da completare: sovrapposizione con debito e altri impegni, completezza di garanzie/acquisti/altri fixed claims, normalizzazione della cassa e conflitti R10F. Le segnalazioni materiali non vengono chiuse sulla sola base di questa riconciliazione. R11 richiede controlli separati e scoring pre-registrato; R12 richiede un esecutore clean-room estraneo alla conversazione di sviluppo. Il progetto non è ancora al 100% operativo.

## Riproduzione

Usare `requirements-r10f.txt` e il verificatore R10F invariato. Il workflow R10G scarica l'artifact R10E `r10e-primary-evidence-36336222379-1` dal run 36336222379, verifica il registro R10G e confronta la ricevuta con quella depositata. Il confronto byte per byte protegge anche gli hash del registro e del verificatore. Gli artifact hanno scadenza; URL, accession e hash dei documenti sono conservati nel registro per un eventuale recupero verificato.
