# Investment OS Data Bridge — stato

Aggiornato: **2026-11-22T21:00:28+00:00**

- Righe universo equity-like: **504**
- Ticker con CIK SEC mappato: **99.8%**
- Società con filing annuale individuato: **99.0%**
- Società con >=90% core metric coverage: **93.8%**
- Ultimo SEC Financial Statement Data Set disponibile: **2026Q3**
- Fondamentali costruiti usando trimestri: **2025Q4, 2026Q1, 2026Q2, 2026Q3**

## Importante

La copertura qui è una misura tecnica, non un BQS. Metriche non appropriate a un settore possono essere `NOT_APPLICABLE` nel successivo processo di analisi. Prima di BUY/ADD i finalisti devono essere verificati contro gli ultimi filing e fonti primarie.
## V4.1 enrichment BR-01 / BR-02

- SEC quarterly datasets usati per lo storico: **16** (2022Q4 → 2026Q3)
- Storico ricavi a 4 esercizi: **93.8%**
- Storico operating income a 4 esercizi: **74.4%**
- Storico FCF a 4 esercizi: **83.5%**
- Storico diluted shares a 4 esercizi: **93.3%**
- SBC corrente disponibile: **93.5%**
- Revenue CAGR 3y calcolabile: **93.7%**
- Operating-income CAGR 3y calcolabile: **63.9%**
- FCF CAGR 3y calcolabile: **67.3%**
- FCF/share CAGR 3y calcolabile: **64.9%**

`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
## V4.1 enrichment BR-03

- SEC quarterly datasets usati: **16** (2022Q4 → 2026Q3)
- `annual_buyback` disponibile: **81.2%**
- `annual_dividends_paid` disponibile: **77.8%**
- `buyback_accretion` disponibile/N.A.: **77.8%**
- `payout_ratio` disponibile: **73.8%**
- `BUYBACK_TAG_ABSENT_CF_PRESENT`: **17.7%**
- `DIVIDENDS_TAG_ABSENT_CF_PRESENT`: **21.0%**
- `NO_BUYBACK_NO_SBC`: **0**
- `PAYOUT_NEGATIVE_EARNINGS`: **27**
- `SHARE_COUNT_DISCONTINUITY`: **11**
- Buyback tag usage: **{"PaymentsForRepurchaseOfCommonStock": 395, "PaymentsForRepurchaseOfEquity": 7, "TreasuryStockValueAcquiredCostMethod": 7}**
- Dividend tag usage: **{"PaymentsOfDividends": 134, "PaymentsOfDividendsCommonStock": 238, "PaymentsOfOrdinaryDividends": 20}**
- Bridge regression checks: **16/16 passed**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
## V4.1 enrichment BR-05

- Fonte primaria market data: **Nasdaq public stock screener**
- Fallback: **FMP stable single-symbol quote, solo per righe mancanti/incomplete**
- Prezzo + market cap direttamente disponibili: **99.6%**
- Market cap ricostruita da bridge shares: **NO**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
- Source counts: **{"MISSING": 2, "NASDAQ_PUBLIC_SCREENER": 502}**
