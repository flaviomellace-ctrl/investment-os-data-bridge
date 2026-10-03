# V4.2 R10J — BR09 documentary review

Data: 3 ottobre 2026. **Sistema NOT LIVE**. Revisione storica sugli accession congelati R10E, non classificazione del portafoglio attuale.

## Risultato

Dieci modelli di business esaminati con 19 estratti da filing primari: cinque negative documentali e cinque classificazioni ancora PROVISIONAL. Nessuna modifica al classifier congelato, ai moduli effettivi, al ranking o a V4.1. Non è una validazione indipendente.

| Società | Conclusione documentale | Effetto |
|---|---|---|
| GM | Produzione/vendita veicoli e captive financing; wholesale volume misura vendite proprie | Modello descritto negativo, mantenere modulo |
| TROW | Advisory fees sullo stock AUM, non sul volume transazionale intermediato | Modello descritto negativo, preservare IOS_BANK |
| NEM | Produzione e vendita di metalli propri | Modello descritto negativo, mantenere modulo |
| FIX | Prestazione diretta di contracting MEP | Modello descritto negativo, mantenere modulo |
| ANET | Vendita di prodotti EOS/hardware e PCS; network è tecnologico | Modello descritto negativo, mantenere modulo |
| FISV | Reti issuer/merchant e commissioni transaction-based: evidenza positiva delle due condizioni nelle attività descritte | PROVISIONAL sul routing consolidato e KPI; triage negativo non sufficiente |
| AMP | Wealth/brokerage/distribution/banking/insurance misti | PROVISIONAL; perimetro economico e volume da definire |
| ADBE | Software diretto e attività advertising nel segmento misto | PROVISIONAL per il gruppo; esaminare advertising prima di negativa globale |
| CMCSA | Connectivity/media/advertising con audience e advertiser | PROVISIONAL; audience non automaticamente volume BR09 |
| FOX | Content, affiliate fees e advertising, incluse piattaforme digitali | PROVISIONAL; perimetro advertising da decidere |

Le cinque negative chiudono la verifica BR09 del modello documentato, non la due diligence complessiva. Nessun ricavo, AUM, subscriber count, viewership o produzione propria viene convertito in underlying volume intermediato. I giudizi umani non sono certificati semanticamente dal workflow.

## Fiserv: lacuna sostanziale emersa

Il filing descrive Accel, STAR e MoneyPass, disponibili a issuer e merchant, e processing services remunerati con fee account/transaction-based. È evidenza sostanziale da confrontare con le prime due domande BR09, non solo una parola “platform”. Il precedente triage negativo non può essere usato come prova di assenza.

La revisione non introduce una soglia nuova per decidere il routing di gruppi misti e non applica una whitelist. Si mantiene il modulo effettivo precedente, ma la revisione documentale resta PROVISIONAL. Se la correzione richiedesse una nuova regola economica dopo il ranking, servirebbe un change request separato; non tuning V4.2 in-place.

## Readiness: distinzione verificata

Le criticità di un titolo non significano automaticamente FAIL dell'intero motore: un Gate correttamente prudente può escluderlo da BUY/ADD. Tuttavia il contratto `V4_2_R10D_PRE_RUN.md` richiede esplicitamente che classificazioni BR09 provisional e flag R6/R7 siano trattati prima della validazione blind indipendente. R10F–I forniscono verifiche e disposizioni, ma non risolvono tutti i perimetri e le normalizzazioni. Non si dichiara READY usando soltanto workflow verdi.

R11 non eseguito: controlli sealed/non-current separati e scoring preregistrato non ancora attestati. R12 non eseguito: questo esecutore ha visto lo sviluppo e non può autocertificarsi clean-room. Bootstrap, IPS e operatività restano non autorizzati dal protocollo. Case closures complessive: zero.

## Riproduzione

Il registro conserva accession, filing date, URL, full-source SHA-256, metodo di normalizzazione, offset e SHA dell'estratto, risposte alle domande e motivazione. Il workflow scarica lo stesso artifact R10E e verifica byte/estratti e coerenza delle disposizioni. Conserva i moduli effettivi e vieta BUY/ADD nel registro. Otto test di integrità R10F invariati restano separati dalla valutazione economica.
