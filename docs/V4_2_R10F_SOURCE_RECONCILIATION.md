# V4.2 R10F — Riconciliazione delle fonti

Data: 28 settembre 2026. Sistema **NOT LIVE**.

## Risultato

Verificati 13 elementi in 9 società contro i filing integrali archiviati da R10E: hash del documento, identificatore del fatto, attributi, valuta, periodo e dimensioni contabili. Otto test sintetici superati. Gli elementi sono supplementi documentati; nessun dato congelato o punteggio viene sostituito automaticamente.

| Società | Elemento | USD | Stato |
|---|---|---:|---|
| ADBE | annual_DA | 818,000,000 | SOURCE_RECONCILED |
| FISV | annual_DA | 3,161,000,000 | SOURCE_RECONCILED |
| FIX | annual_DA_face_statement | 141,959,000 | CONFLICTING_EXTERNAL_AGGREGATE |
| FOX | cash_and_equivalents_face_statement | 5,351,000,000 | SOURCE_RECONCILED_WITH_LABEL_REVIEW |
| FOX | operating_income_derived | 2,879,000,000 | DERIVED_NOT_DIRECT_TAG |
| NEM | operating_income_derived | 10,961,000,000 | DERIVED_NOT_DIRECT_TAG |
| GM | debt_carrying_amount_face_statement | 130,277,000,000 | SOURCE_RECONCILED_SCOPE_REVIEW_REQUIRED |
| AMP | cash_excluding_consolidated_investment_entities | 9,953,000,000 | SOURCE_RECONCILED_SCOPE_REVIEW_REQUIRED |
| AMP | debt_excluding_consolidated_investment_entities | 3,277,000,000 | SOURCE_RECONCILED_SCOPE_REVIEW_REQUIRED |
| AMP | debt_consolidated_investment_entities | 2,585,000,000 | SOURCE_RECONCILED_SCOPE_REVIEW_REQUIRED |
| ADBE | purchase_obligations | 6,821,000,000 | QUANTIFIED_CATEGORY_ONLY |
| ANET | purchase_obligations | 6,800,000,000 | QUANTIFIED_CATEGORY_ONLY |
| TROW | mixed_DA_impairment_retention_lines | 605,500,000 | NOT_ACCEPTED_AS_PURE_DA |

## Correzioni e limiti

- **Adobe:** recuperati 818 milioni di D&A; il periodo effettivo dello stesso accession è 28 novembre 2025. Non si introduce una tolleranza generalizzata sulle date.
- **Fiserv:** i due addendi distinti del rendiconto sono 1.857 e 1.304 milioni, per 3.161 milioni. Il dato precedente di 669 milioni copriva solo il deprezzamento. I 46 milioni di ammortamento finanziario sono esclusi; non si sommano di nuovo componenti sovrapposte.
- **FOX:** recuperata cassa per 5.351 milioni; risultato operativo derivato di 2.879 milioni. Il secondo è un calcolo esplicito dai prospetti, non un tag riportato direttamente. Le spese di ristrutturazione non vengono aggiunte indietro.
- **Newmont:** risultato operativo derivato di 10.961 milioni; include svalutazioni e plusvalenze come presentate, senza normalizzazione.
- **GM:** debito contabile dai quattro importi di stato patrimoniale pari a 130.277 milioni. Il prospetto scadenze/principale di 131.574 milioni usa una base diversa; non viene sostituito al valore contabile.
- **Ameriprise:** cassa e debito dell’emittente sono separati da quelli delle entità di investimento consolidate. Rimane da assicurare coerenza del perimetro con il denominatore del rapporto di leva.
- **Comfort Systems:** D&A dai due importi del rendiconto pari a 141,959 milioni. Companyfacts riporta 79,578 milioni per l’ammortamento immateriale, mentre il filing mostra 79,580 milioni. La differenza di 2.000 USD resta CONFLICTING, senza selezione silenziosa.
- **T. Rowe Price:** i 605,5 milioni delle due righe includono impairment e retention arrangements; la somma non è accettata come D&A puro.
- Quantificati due gruppi di impegni d’acquisto: Adobe 6,821 miliardi, Arista 6,8 miliardi arrotondati. Non equivalgono al totale degli impegni né al debito.

## Stato delle verifiche successive

Le correzioni di fonte non chiudono la due diligence: restano normalizzazione della cassa, perimetri e sovrapposizioni degli impegni, completezza del debito e conflitti documentati. I controlli R11 e la validazione indipendente R12 restano successivi a queste riconciliazioni. Il sistema non è al 100% operativo.

## Riproduzione

Dipendenza isolata: `python -m pip install -r requirements-r10f.txt`. Scaricare l’artifact `r10e-primary-evidence-36336222379-1` del run 36336222379, estrarlo e usare la cartella `_temp/r10e_primary_sources`.

```bash
python tests/test_r10f_source_corrections.py
python src/r10f_verify_source_corrections.py \
  --registry data/v4_2/r10f/review_20260928/V4_2_R10F_REVIEWED_SOURCE_CORRECTIONS.json \
  --sources /percorso/estratto/_temp/r10e_primary_sources \
  --output /percorso/nuovo_receipt.json
```

Il workflow R10F ripete questi controlli in sola lettura, confrontando il receipt con quello prodotto localmente. Gli artifact GitHub hanno scadenza; il registro conserva URL, accession e hash per recuperare e verificare nuovamente i documenti primari.
