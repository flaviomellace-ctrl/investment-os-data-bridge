# V4.2 R10K — Cash scope bridges and Claude handoff

Data: 3 ottobre 2026. **NOT LIVE**. Per il progetto Investment OS in Claude: questa consegna supporta la prosecuzione dello sviluppo, non certifica operatività né rendimento.

## Problemi risolti a livello di fonte e perimetro

| Caso | Ponte verificabile | Conclusione |
|---|---|---|
| CMCSA investimenti | PPE capex 11.750 + intangibili 2.658 + Beijing 11 = 14.419 milioni USD | Risolto quali pagamenti sono fuori dal tag PPE usato nel calcolo congelato |
| CMCSA owner cash | OCF 33.643 − investimenti ampliati 14.419 − SBC 1.288 = 17.936 milioni USD | Sensibilità documentata, non normalized OE completo |
| CMCSA differenza | 20.605 − 17.936 = 2.669 milioni USD, 12,953% dell'OE aritmetico congelato | Supera la soglia diagnostica R6 congelata del 10%; riconciliazione materiale, non cambio IOS |
| TROW perimetro OCF | Gruppo 2.489,5 + prodotti consolidati −797,3 + eliminazioni 61,2 = consolidato 1.753,4 milioni USD | Risolta la separazione documentale OCF gruppo/prodotti, senza add-back arbitrari |
| GM perimetro automotive | Filing descrive OCF automotive 18,7 miliardi e capex 9,2 miliardi, arrotondati; management adjustments 1,1 miliardi separati | Non usare OCF consolidato 26,867 miliardi come OCF automotive; FCF adjusted management non è OE del modello |

La sensibilità Comcast non afferma che ogni investimento sia maintenance capex; l'inclusione estesa mostra l'effetto della copertura dei pagamenti identificati. Non si aggiungono acquisizioni o interi portafogli finanziari al capex in modo indiscriminato. Il motore e il ranking congelati rimangono invariati.

## Nuova evidenza fiscale Comcast

Il ponte MD&A riporta pagamenti netti di imposte 755 milioni nel 2025 contro 7.096 milioni nel 2024. Il filing attribuisce il calo a imposte 2024 sul gain Hulu 2023, rimborso federale 2025 da carryback di una perdita di capitale, nuove deduzioni legislative e timing dei tax credit. Il confronto non è interamente un beneficio temporaneo ripetibile né un importo da sottrarre automaticamente. Occorre separare rimborso non ricorrente e deduzioni con durata pluriennale; normalized OE resta MISSING. Il vecchio scan senza cash flag non costituiva clearance fiscale.

## GM: scomposizione del capitale circolante

Nota 24: crediti +846, wholesale receivables funded by GM Financial +2.633, inventari +626, altri attivi +214, debiti fornitori −2.145, imposte payable +39, accrued/other liabilities +6.844 = +9.056 milioni USD. La somma chiude il ponte consolidato. Non prova che i 9.056 milioni siano tutti temporanei; il rapporto con captive finance, wholesale financing e sostenibilità dei passivi resta da esaminare.

## TROW: cosa è chiuso e cosa no

La tabella MD&A non è un inline fact numerico: viene verificata come tabella documentale, con hash del filing, excerpt, struttura della riga e celle. Non viene travestita da XBRL. La fonte distingue OCF attribuibile al gruppo, prodotti consolidati ed eliminazioni. Non si aggiungono indietro automaticamente i 1.002,7 milioni di acquisti di trading securities: il ponte completo include anche eliminazioni. Resta da allineare il perimetro degli altri input; la variante IOS_BANK non cambia.

## Istruzioni di consegna a Claude

Il progetto in Claude resta il luogo in cui proseguire verso l'operatività. Il pacchetto è un **supplemento di evidenze R10E–K**, non un nuovo motore, non un freeze finale e non un ordine di trading.

1. Conservare V4.1, le formule BQS/IOS, Lane I, quota 7+3 e soglie congelate. Non applicare automaticamente i valori revisionati al ranking.
2. Verificare hash e receipt; distinguere numeric source PASS, interpretazione economica e case closure. Un workflow verde non chiude il dossier.
3. Usare R10F–K per risolvere i singoli input: capex Comcast; perimetri TROW/AMP/GM; D&A FIX; leasing e impegni per categoria e sovrapposizione; BR09 gruppi misti.
4. Non trasformare MISSING in zero o normalizzazioni incomplete in valori PRESENT. FISV ha evidenza positiva nelle attività di network/processing, non autorizzazione a introdurre nuove regole consolidate dopo il ranking.
5. Per ogni flag residuo registrare fonte, conclusione, effetto sul Gate e criterio di chiusura. Un candidato con red flag materiale resta INVESTIGARE/PROVISIONAL e non BUY/ADD.
6. Ricostruire e sigillare il pacchetto completo del motore congelato prima dei test: full ranking, lookup, lanes, queue, market/canonical snapshots, engine/adapter/classifier hashes, regole e ricevute di regressione. Questo ZIP supplementare non contiene tutti questi elementi.
7. R11: controlli sealed/non-current separati e scoring preregistrato prima dell'apertura. Non usare i candidati R10 conosciuti come controlli hidden.
8. R12: esecutore che non ha visto validation nota né conversazione di sviluppo, riceve solo frozen artifacts e safe methodology. Se il progetto Claude contiene già sviluppo e validation, usarlo come sviluppatore/orchestratore, non autocertificarlo clean-room. È necessario un contesto indipendente separato.
9. Solo dopo PASS secondo criteri preregistrati: Bootstrap/IPS/ledgers/dry-run. Broker auto-execution OFF. L'attivazione operativa resta distinta dal completamento di questo supplemento.

R10K risolve i ponti documentali indicati. Normalizzazione completa, routing misto, due diligence complessiva, R11/R12 e operatività non sono dichiarati conclusi. Non è necessario ripartire da zero: le evidenze già verificate sono conservate e versionate.
