# V4.2 R10N — leverage da input primari verificati

3 ottobre 2026. Revisione storica sugli accession congelati R10E. Sistema NOT LIVE.

## Risultato

Trenta input verificati direttamente nei filing primari, con hash del file completo, ID inline XBRL, contesto annuale/istantaneo, valuta USD e attributi esatti. Sei viste secondarie calcolate con il modulo R6/R7 congelato; controllo aritmetico indipendente con Decimal. Nessuna modifica a motore, canonical, BQS, IOS, ranking o coda.

Il rapporto è debito contabile riportato / (risultato operativo riportato + D&A - SBC). È una vista contabile secondaria, non EBITDA normalizzato o covenant leverage. Soglie congelate: CAUTION >=3, HIGH >=4. BELOW_CAUTION non equivale a clearance.

| Società | Rapporto dopo SBC | Banda | Progresso verificato |
|---|---:|---|---|
| FISV | 3,3631 | CAUTION | D&A completo 3.161m; il precedente 669m era sola depreciation |
| CMCSA | 2,7796 | BELOW_CAUTION | DebtCurrent 5.958m + noncurrent debt/capital leases 92.979m; nessuna aggiunta duplicata dei finance leases |
| ADBE | 0,8190 | BELOW_CAUTION | Vista prima MISSING ora calcolabile; periodo effettivo 28 novembre 2025, debito carrying 6.210m |
| FOX | 2,1099 | BELOW_CAUTION | Vista prima MISSING ora calcolabile; cassa 5.351m e operating income derivato 2.879m, filing 2025 |
| NEM | 0,3822 | BELOW_CAUTION | Vista prima MISSING ora calcolabile; current debt zero esplicitamente dichiarato + noncurrent 5.115m |
| FIX | 0,1012 | BELOW_CAUTION | D&A 141,959m corretto da R10L, senza falso conflitto; debito carrying 145,226m |

Tre viste precedentemente MISSING sono ora calcolabili. FISV e FIX correggono input incompleti già numerici; CMCSA ricostruisce i componenti della voce debito. Questo non riscrive i precedenti overlay, che restano ricevute storiche.

## Perimetri preservati

- FISV: il debito include finance leases e altri finanziamenti; settlement cash non aggiunto alla cassa libera.
- ADBE: carrying debt 6.210m distinto dal principal 6.150m; nessun ricalcolo retroattivo del bridge.
- FOX/NEM: operating income derivato con le rettifiche R10F, senza add-back automatico di impairment, ristrutturazioni o plusvalenze. La cassa totale riportata non è un'attestazione di liquidità interamente distribuibile.
- FIX: leasing operativo, surety e obblighi restano separati e aperti; la correttezza della D&A non chiude il dossier.

Le passività operative o fuori bilancio non sono aggiunte automaticamente al numeratore. Il trattamento completo di debito, leasing, restricted cash, garanzie e obblighi richiede riconciliazione separata. Queste viste non attestano la solvibilità o la cassa disponibile per investire.

## Esclusioni motivate

GM: il consolidato comprende captive finance; serve separare debito, cassa ed EBITDA automotive/financial prima di un giudizio industriale.

AMP: perimetro finanziario/assicurativo e consolidated investment entities; non trattare la leva industriale come clearance del capitale regolamentare.

TROW: preservare IOS_BANK. Il vecchio aggregato D&A/impairment/retention non è D&A pura; nessuna imputazione arbitraria.

ANET: debito finanziario MISSING; assenza di un tag non significa zero. I pagamenti leasing 90,5m non sono la passività attualizzata.

## Disposizione e requisiti rimanenti

Tutti i sei casi conservano HOLD_UNRESOLVED_NO_BUY_ADD, normalized_owner_earnings=MISSING, normalization_complete=false e economic_case_closed=false. Le questioni BR09, cash quality e obblighi restano aperte. Nessuna azione finanziaria è stata emessa.

R11 e R12 non sono eseguiti da questa revisione. Rimangono necessari i controlli separati e una validazione con esecutore indipendente. Il Project Claude esistente e il pacchetto personale 4.0 restano il riferimento operativo; non viene generato un nuovo pacchetto finale o modificata la Costituzione.

## Riproduzione

`r10n_verified_leverage_view.py` legge selezioni da dati revisionati, verifica tutte le fonti tramite il checker R10F e controlla l'hash R6/R7 prima dei calcoli. Le selezioni di società e fact ID sono esclusivamente nel registro dati. L'esecuzione produce una ricevuta nuova e deve coincidere byte per byte con quella revisionata; non sovrascrive input congelati.
