# V4.2 R10I — Cash quality and disposition review

Data: 28 settembre 2026. **NOT LIVE — NOT READY FOR R11/R12**.

## Esito

Verificati sul medesimo accession congelato 30 input (OCF, capex, SBC), 10 calcoli aritmetici OE e 10 rendiconti finanziari completi. Fonte: artifact R10E 10937655129, run 36336222379, SHA-256 de766c06c2669ba93183bf9c58d5aa038cc340d5bb3057408966b1d2ef91327e. La verifica numerica usa il verificatore R10F invariato. Questi riscontri non certificano normalizzazione, disponibilità della cassa o completezza del capex economico.

Tutti i dieci casi ricevono disposizione istruttoria esplicita INVESTIGARE, confidence PROVISIONAL, cash gate RECONCILE_CASH_QUALITY, BUY/ADD non consentito. Non è una riclassificazione automatica nel motore: è il registro della revisione documentale. Nessun caso chiuso; nessun punteggio, ranking, motore, soglia o baseline V4.1 modificato.

## Cash review per candidato

OE riportato sotto significa esclusivamente OCF meno il capex congelato meno SBC. Non è una nuova valutazione né una stima di rendimento. Per i gruppi finanziari non sostituisce le varianti IOS congelate.

| Società | OE aritmetico, milioni USD | Stato della revisione |
|---|---:|---|
| ADBE | 7,910.000 | TAX_SIGNAL_NOT_PROVEN_ANOMALY |
| AMP | 7,955.000 | FINANCIAL_PERIMETER_UNRESOLVED |
| ANET | 3,813.200 | WORKING_CAPITAL_RECONCILIATION_REQUIRED |
| CMCSA | 20,605.000 | CAPEX_SCOPE_AND_WORKING_CAPITAL_REVIEW |
| FISV | 3,942.000 | ADVANCES_AND_SETTLEMENT_PERIMETER_REVIEW |
| FIX | 1,009.644 | WORKING_CAPITAL_RECONCILIATION_REQUIRED |
| FOX | 2,858.000 | WORKING_CAPITAL_AND_ONE_OFF_REVIEW |
| GM | 17,230.000 | CAPTIVE_FINANCE_AND_WORKING_CAPITAL_REVIEW |
| NEM | 7,200.000 | NONCASH_REVERSAL_RESOLVED_TAX_TIMING_OPEN |
| TROW | 1,262.300 | CONSOLIDATED_PRODUCTS_PERIMETER_REVIEW |

### ADBE

Il testo intercettato riguarda incertezza futura sugli accertamenti, non dimostra un beneficio temporaneo nell’OCF 2025. Imposte differite -512m già riconciliate nel rendiconto; imposte pagate 2219m. Non sottrarre di nuovo le imposte differite. La riga investimenti/intangibili/altri beni 134m richiede separazione prima di affermare completezza economica del capex.

### AMP

OCF include +4610m da saldi assicurati, benefici e market risk benefits; non equivale a cassa distribuibile. Portafoglio investimenti e passività devono essere trattati insieme. Riserva liberata nella nota non è automaticamente cash flow. Applicare variante finanziaria congelata, non generic OE come misura operativa.

### ANET

Deferred revenue +2452m, contro assorbimenti crediti 746.4m, inventari 412.5m e altri attivi 937.4m. Il contributo non è tutto profitto ricorrente né tutto beneficio temporaneo: analizzare contratti e recupero degli anticipi prima di normalizzare. Capex include intangibili.

### CMCSA

Oltre al capex 11750m compaiono 2658m pagati per intangibili e 11m per Universal Beijing. Il calcolo congelato non incorpora queste righe: completezza del capex da riconciliare senza modificare formula o ranking. Guadagni investimenti -8853m già stornati nella riconciliazione OCF; altre attività/passività +1994m da spiegare.

### FISV

Capex 1763m include software e altri intangibili. Merchant advances 1129m e rimborsi 1018m, settlement anticipation advances netti 525m sono investing; settlement activity 222m è financing. Non confondere settlement cash con cassa disponibile. Imposte differite -942m già nel ponte OCF.

### FIX

Billings in excess/deferred revenue +910.084m contro crediti -594.298m e debiti/altri passivi correnti -276.051m. Non sottrarre l’intero anticipo senza ricostruire i costi coperti; non aggiungere automaticamente gli assorbimenti. Fair value earn-out 33.473m già nel ponte OCF. Rimane il conflitto D&A di R10F.

### FOX

Inventories net of programming payable +521m; restructuring/impairment/other corporate matters +267m nel ponte. Distinguere cash settlements e noncash adjustments. Nessuna add-back automatica. Si usa il filing congelato al 30 giugno 2025, non il successivo 2026.

### GM

OCF consolidato include +9056m da altri attivi/passivi operativi; investing include acquisti veicoli in leasing 15793m e realizzi 10095m, oltre ai crediti finanziari. OCF meno solo property capex non rappresenta direttamente cassa automotive distribuibile. Il riferimento a reserve release riguarda 2024, non prova beneficio 2025. SBC 334m confermato nella nota compensi.

### NEM

Variazione fair value -604m e plusvalenza cessioni -1066m sono già rettifiche nel ponte OCF: non sottrarle nuovamente. Accrued tax liabilities +1039m e deferred taxes +1391m richiedono riconciliazione dei tempi fiscali; reclamation liabilities -803m richiede confronto con obblighi futuri. SBC 99m confermato in nota e rendiconto.

### TROW

Fair value contingent consideration nel 2025 è zero (2024 -13.4m); gains investments -452.4m già rettificati. Trading securities dei prodotti consolidati assorbono 1002.7m: non aggiungerli indietro senza separare perimetro emittente, prodotti e interessenze terzi. OE aritmetico non sostituisce IOS_BANK.

## Decisioni sui segnali precedenti

- Adobe: il match lessicale sulle date dei pagamenti fiscali è un avviso generale su audit futuri; non è prova di un'anomalia OCF corrente. Il subitem lessicale è reinterpretato, ma non si dichiara completa la normalizzazione.
- GM: il reserve release citato riguarda l'anno precedente. Non si attribuisce automaticamente quel beneficio al 2025. Restano captive finance e capitale circolante.
- Newmont: plusvalenze e fair value sono già stornati nel ponte OCF; una seconda sottrazione sarebbe doppio conteggio. Restano riconciliazione fiscale e reclamation.
- TROW: il remeasurement contingente del 2025 è zero; le cifre del 2024 non diventano aggiustamenti 2025. Restano prodotti consolidati e perimetro.
- Assenza di flag lessicali non significa cash quality verificata: FIX, ANET, FOX, CMCSA e FISV presentano questioni documentate da esaminare.

Non viene scelto alcun aggiustamento arbitrario. Normalized OE resta MISSING/null e normalization_complete=false per tutti: l'assenza di evidenza sufficiente non è zero. Le righe di capitale circolante non sono tutte temporanee e non sono sommabili a priori con imposte o componenti noncash.

## Registro dei blocchi e condizioni di chiusura

| Ambito | Decisione attuale | Evidenza necessaria per chiudere |
|---|---|---|
| R6 cassa | RECONCILE_CASH_QUALITY per i 10 casi | Ponte perimetro coerente; componenti temporanee documentate e assenza di doppio conteggio; capex completo oppure limite esplicito |
| R7 impegni | INVESTIGARE | Matrice completa per categoria, scadenze e sovrapposizioni con debito, leasing, cash flow e impegni contingenti; R10H quantifica solo categorie |
| Leva | PROVISIONAL | Debito completo e denominatore sullo stesso perimetro; conflitto FIX e differenze CMCSA/GM conservati; ANET lease liability non ricostruita da pagamenti |
| BR09 | Classificazione sostanziale non chiusa | Modello di ricavo e due popolazioni economiche documentati; triage negativo non sufficiente; niente whitelist nel codice |
| R11 | NOT RUN / BLOCKED | Controlli sealed/non-current separati, scoring preregistrato, prerequisiti di regressione e freeze verificati |
| R12 | NOT RUN / BLOCKED | Esecutore clean-room che non vede questa conversazione né validation nota; pacchetto frozen e safe methodology soltanto |
| Bootstrap / IPS / dry-run | BLOCKED | R11/R12 PASS secondo criteri preregistrati, Gate operativo, broker auto-execution OFF |

Il protocollo docs/V4_2_REGRESSION_PLAN.md e docs/V4_2_CHANGE_CONTROL_SPEC.md vieta di sostituire R11/R12 con i controlli di integrità di fonte. Questo esecutore ha visto lo sviluppo e non può certificare la propria indipendenza. Non sono stati inventati controlli nascosti né aperti validation set. Non si fissa una soglia di PASS dopo aver visto i risultati.

## Riproduzione

Il workflow v4-2-r10i-cash-review.yml scarica il medesimo artifact R10E, esegue gli otto test di integrità R10F, verifica i 40 elementi con sorgenti/hash/periodi/dimensioni/unità, confronta il receipt, verifica gli estratti e controlla la coerenza delle disposizioni. I controlli automatici attestano integrità e coerenza del registro, non la correttezza completa dei giudizi economici. Nessun ranking viene ricalcolato.
