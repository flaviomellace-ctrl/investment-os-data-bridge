# R12-quater — esito con criteri R12 v2 (date 14/11/2014, 16/11/2015, 15/11/2016, 15/11/2017)

Congelamento: `docs/r12/R12_CRITERIA_V2_AND_R12QUATER_FROZEN_2026-11-22.md` (sha d498391c…), approvato da Flavio.
Esecutore indipendente: `EXECUTOR_REPORT.json` (sha 409154db…, run1 = run2 su tutte le date). Rendimenti Yahoo
adjclose letti dopo il congelamento; trascrizione verificata con hash (f4cec1476bd871c5, 4e8613c1ca51d111,
90c3f32f733a360d, fc758401d5494284). Calcolo: `R12QUATER_SCORING.json`.

| Criterio | Esito | Dato |
|---|---|---|
| C1 integrità temporale | SUPERATO | nessuna data successiva; run identici; 0 buy_add_allowed |
| C2 IOS calcolabile ≥ 25% | SUPERATO | 25,1% · 30,1% · 28,9% · 31,1% |
| M1 v2 crolli non significativamente sopra l'universo | **FALLITO** | 3 crolli su 38 contro 0,77 attesi; p = 0,041 < 0,05 |
| M2 mediana non > 10 punti sotto | SUPERATO (al limite) | coda +16,4% contro universo +22,4% (−6,1 punti) |

Crolli: Fossil (coda 2015) −76,1%; Alliance Data (coda 2017) −52,6%; Signet Jewelers (coda 2017) −74,5%.
Esclusi per acquisizione (regola congelata): AGL Resources (coda 2014, acquisita da Southern Company il 01/07/2016)
e Aetna (coda 2016, acquisita da CVS il 28/11/2018).
Mediane per data: 2014 coda −28,4% contro +13,2%; 2015 +24,0% contro +31,7%; 2016 +0,7% contro +25,1%;
2017 +15,4% contro +21,4%. La coda è sotto l'universo in tutte e quattro le date.

## Verdetto
R12 NON SUPERATO anche con i criteri v2. Registrato. Nessun nuovo tentativo sulle stesse date.

## Lettura
Su dieci date (2014-2024) la coda batte l'universo nel 2018-2023 e perde nel 2014-2017 e nel 2024. I crolli in coda
hanno un tratto comune: aziende a basso multiplo con utili poi crollati (Fossil, Signet, Alliance Data; prima Deckers,
Lululemon, Builders FirstSource). È il classico "value trap": il prezzo basso riflette un deterioramento che i
bilanci passati non mostrano ancora. È un difetto del modello, non dei dati né del test.
