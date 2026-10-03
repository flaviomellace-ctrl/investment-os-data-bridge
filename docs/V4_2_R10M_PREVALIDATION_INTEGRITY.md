# V4.2 R10M — integrità e riproducibilità prima della validazione

3 ottobre 2026. Verifica di sviluppo. Sistema **NOT LIVE**.

## Controlli

- Hash del motore V4.1 e del motore V4.2 invariati; classifier, Lane I e R6/R7 coincidono con il manifest congelato.
- Esecuzione delle sei suite originali: baseline V4.1, marketplace R2/R3, inflection R4/R5, cash/commitments R6/R7, varianti R8 e integrazione V4.2.
- Riproduzione isolata R10C dal dataset e dalla provenienza R10B originali: la comparazione completa delle 504 righe deve coincidere **byte per byte** con il risultato congelato.
- Collegamento della coda 7+3 alle disposizioni cash R10I e BR09 R10J. Nessuna sostituzione di titoli, nessuna riscrittura del ranking.
- Verifica del Gate congelato anche simulando sistema LIVE e Gate qualitativo completato: una red flag materiale irrisolta impedisce comunque BUY/ADD. La simulazione è una chiamata locale alla funzione, non un'attivazione LIVE.

Le fonti Companyfacts e i registri non vengono interpretati come prova di completezza economica. R10L corregge esplicitamente il falso conflitto D&A FIX: la correzione del singolo dato non rimuove gli altri flag del dossier.

## Decisione sui residui

Le dieci società della coda conservano `HOLD_UNRESOLVED_NO_BUY_ADD`. Si documenta il blocco operativo dei rischi noti, senza trasformare normalizzazioni incomplete in numeri, senza azzerare MISSING e senza dichiarare chiusi i casi economici.

Il ledger è un consolidamento dei blocchi già documentati, **non** una clearance, un giudizio di vendita o una selezione alternativa. La coda storica rimane 7+3. I rischi non quantificabili non devono essere forzati a PASS per raggiungere una percentuale.

## Limite di readiness

Un Gate che blocca correttamente i casi irrisolti è una proprietà verificabile del motore. Non sostituisce il requisito R10D di trattare BR09 provisional e R6/R7 prima della blind validation. R10M non certifica R11-ready e non esegue R11 o R12.

R11 richiede controlli sealed/non-current separati e scoring preregistrato. R12 richiede un esecutore che non abbia visto sviluppo e validation nota, e riceva solo il pacchetto congelato e la metodologia sicura. Questi test restano distinti dalle suite sintetiche esistenti e dalla riproduzione R10C.

I risultati vengono conservati come artefatto GitHub del run, con receipt, ledger e log. Il supplemento per Claude rimane intermedio; la consegna finale sarà successiva alla validazione, senza modificare V4.1 o le regole congelate.
