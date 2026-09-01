# Investment OS Data Bridge

Ponte dati gratuito e automatico per `Investment OS`.

## Cosa fa

Ogni lunedì GitHub Actions:

1. scarica le holdings correnti di **SPY** da State Street;
2. scarica la mappa ticker → CIK ufficiale SEC;
3. controlla qual è l'ultimo **SEC Financial Statement Data Set** disponibile;
4. se è comparso un nuovo trimestre SEC, scarica automaticamente gli ultimi 4 trimestri, apre gli ZIP e ricostruisce i fondamentali dell'universo;
5. produce piccoli file CSV/JSON facili da leggere da Claude;
6. salva e versiona automaticamente l'aggiornamento nel repository GitHub.

Se il trimestre SEC non è cambiato, non riscarica centinaia di MB: aggiorna l'universo e riusa i fondamentali già presenti.

## Fonti pubbliche

- State Street SPY: https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy
- SPY holdings XLSX: https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx
- SEC Financial Statement Data Sets: https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets
- SEC ticker/CIK map: https://www.sec.gov/files/company_tickers.json
- SEC fair-access guidance: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data

## Output per Claude

`data/current/` contiene:

- `sp500_universe.csv`
- `sp500_fundamentals.csv`
- `sp500_coverage.csv`
- `manifest.json`
- `status.md`
- `claude_sources.md`

Il bridge **non sceglie titoli**, non calcola BQS/IOS e non genera BUY. Prepara soltanto dati pubblici e tracciabili.

## Filosofia di sicurezza

- `MISSING` non diventa zero.
- Le metriche di copertura sono tecniche, non giudizi di qualità.
- Nessuna API key è necessaria.
- Nessun dato personale deve entrare nel repository.
- Per i finalisti, Claude deve verificare i numeri contro gli ultimi filing/Investor Relations.
- Il trading automatico resta fuori dal progetto.

## Installazione

Apri `docs/GUIDA_PASSO_PASSO.md` e segui i passaggi nell'ordine indicato.
