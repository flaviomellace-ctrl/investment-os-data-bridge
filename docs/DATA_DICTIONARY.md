# Data Dictionary

## sp500_universe.csv

- `ticker`: ticker come pubblicato da State Street.
- `ticker_sec`: ticker normalizzato per la mappa SEC (`.` → `-` per classi azionarie quando necessario).
- `name`: nome del titolo.
- `sector`: settore State Street, se presente nel workbook.
- `weight`: peso del titolo nel fondo, se disponibile.
- `identifier`: identificatore/CUSIP quando presente.
- `isin`: ISIN quando presente.
- `asset_class`: asset class quando presente.
- `cik`: CIK SEC a 10 cifre.
- `sec_title`: nome società nella mappa SEC.
- `cik_status`: `PRESENT` o `MISSING`.

## sp500_fundamentals.csv

Le colonne `annual_*` derivano dal più recente filing annuale disponibile negli ultimi quattro SEC Financial Statement Data Sets trimestrali utilizzati.

Metriche principali:
- `annual_revenue`
- `annual_net_income`
- `annual_operating_income`
- `annual_operating_cash_flow`
- `annual_capex`
- `annual_fcf`: CFO - |capex|, solo se entrambe le componenti sono presenti.
- `annual_diluted_shares`
- `annual_assets`
- `annual_equity`
- `annual_cash`
- `annual_debt`

Per molte metriche sono conservati anche:
- tag XBRL selezionato;
- data del fatto XBRL;
- valore comparativo precedente quando disponibile nello stesso filing.

Ratio derivati:
- `revenue_yoy`
- `net_income_yoy`
- `diluted_shares_yoy`
- `operating_margin`
- `net_margin`
- `fcf_margin`
- `roe_simple`
- `debt_to_equity`

### Avvertenza settoriale

Queste metriche sono uno screening generico. Non sono tutte appropriate per banche, assicurazioni, REIT, utilities e altri settori speciali. Il bridge non assegna penalità per una metrica mancante; sarà il livello Investment OS a classificare eventuali `NOT_APPLICABLE` usando i moduli settoriali.

## sp500_coverage.csv

Contiene per società:
- presenza del filing annuale;
- copertura delle metriche core;
- copertura delle metriche estese;
- flag di dati mancanti.

`core_metric_coverage_pct` è una misura tecnica di disponibilità, non BQS.

## manifest.json

Conserva:
- timestamp del refresh;
- URL delle fonti;
- hash SHA-256;
- trimestre SEC più recente;
- trimestri usati;
- numero righe universo;
- copertura CIK;
- note metodologiche.
