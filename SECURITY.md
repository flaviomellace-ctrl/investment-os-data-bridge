# Security

Questo repository è progettato per contenere soltanto dati pubblici provenienti da State Street e SEC.

Non committare mai:
- API key FMP o di altri provider;
- password o token;
- dati personali o patrimoniali;
- file dell'IPS personale;
- materiale di validazione del Blind Test;
- credenziali Google/Gmail.

L'unico valore richiesto per il traffico SEC è un indirizzo email di contatto nel secret GitHub `SEC_CONTACT_EMAIL`, usato nel `User-Agent` per rispettare la policy SEC sui download automatizzati. Il secret non viene scritto nei file di output.
