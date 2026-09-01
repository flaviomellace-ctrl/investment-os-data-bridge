# Architettura

```text
State Street SPY holdings XLSX
            |
            v
      sp500_universe.csv
            |
            +---- SEC company_tickers.json ----> ticker -> CIK
            |
            v
SEC Financial Statement Data Sets (ultimi 4 trimestri)
            |
            +---- sub.txt: filing / CIK / period / filed
            +---- num.txt: fatti XBRL numerici
            |
            v
     filtro ai filing S&P 500
            |
            v
  sp500_fundamentals.csv
  sp500_coverage.csv
  manifest.json
            |
            v
       Claude Investment OS
            |
            +--> screening
            +--> BQS (prezzo-indipendente)
            +--> IOS (prezzo/valuation)
            +--> deep dive su fonti primarie aggiornate
            +--> Decision Gate
```

## Aggiornamento incrementale

Il job settimanale controlla sempre State Street e l'indice SEC dei dataset. I grandi ZIP SEC vengono riscaricati soltanto se:

- non esiste ancora uno snapshot fondamentale;
- la SEC ha pubblicato un trimestre nuovo;
- l'utente lancia manualmente il workflow con `force_sec=true`.

Questo riduce traffico inutile verso SEC e tempi di esecuzione.
