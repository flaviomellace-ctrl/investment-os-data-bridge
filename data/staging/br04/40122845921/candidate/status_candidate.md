# Investment OS Data Bridge — stato

Aggiornato: **2026-10-19T10:45:47+00:00**

- Righe universo equity-like: **504**
- Ticker con CIK SEC mappato: **99.8%**
- Società con filing annuale individuato: **100.0%**
- Società con >=90% core metric coverage: **64.1%**
- Ultimo SEC Financial Statement Data Set disponibile: **2026Q3**
- Fondamentali costruiti usando trimestri: **2025Q4, 2026Q1, 2026Q2, 2026Q3**

## Importante

La copertura qui è una misura tecnica, non un BQS. Metriche non appropriate a un settore possono essere `NOT_APPLICABLE` nel successivo processo di analisi. Prima di BUY/ADD i finalisti devono essere verificati contro gli ultimi filing e fonti primarie.
## V4.1 enrichment BR-01 / BR-02

- SEC quarterly datasets usati per lo storico: **16** (2022Q4 → 2026Q3)
- Storico ricavi a 4 esercizi: **85.7%**
- Storico operating income a 4 esercizi: **71.6%**
- Storico FCF a 4 esercizi: **77.8%**
- Storico diluted shares a 4 esercizi: **70.6%**
- SBC corrente disponibile: **80.0%**
- Revenue CAGR 3y calcolabile: **85.5%**
- Operating-income CAGR 3y calcolabile: **62.7%**
- FCF CAGR 3y calcolabile: **63.7%**
- FCF/share CAGR 3y calcolabile: **47.2%**

`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
## V4.1 enrichment BR-03

- SEC quarterly datasets usati: **16** (2022Q4 → 2026Q3)
- `annual_buyback` disponibile: **81.2%**
- `annual_dividends_paid` disponibile: **78.0%**
- `buyback_accretion` disponibile/N.A.: **67.7%**
- `payout_ratio` disponibile: **74.0%**
- `BUYBACK_TAG_ABSENT_CF_PRESENT`: **17.5%**
- `DIVIDENDS_TAG_ABSENT_CF_PRESENT`: **20.6%**
- `NO_BUYBACK_NO_SBC`: **0**
- `PAYOUT_NEGATIVE_EARNINGS`: **27**
- `SHARE_COUNT_DISCONTINUITY`: **9**
- Buyback tag usage: **{"PaymentsForRepurchaseOfCommonStock": 395, "PaymentsForRepurchaseOfEquity": 7, "TreasuryStockValueAcquiredCostMethod": 7}**
- Dividend tag usage: **{"PaymentsOfDividends": 135, "PaymentsOfDividendsCommonStock": 238, "PaymentsOfOrdinaryDividends": 20}**
- Bridge regression checks: **16/16 passed**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
## V4.1 enrichment BR-05

- Fonte primaria market data: **Nasdaq public stock screener**
- Fallback: **FMP stable single-symbol quote, solo per righe mancanti/incomplete**
- Prezzo + market cap direttamente disponibili: **99.6%**
- Market cap ricostruita da bridge shares: **NO**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
- Source counts: **{"MISSING": 2, "NASDAQ_PUBLIC_SCREENER": 502}**

## V4.1 enrichment BR-04 — S1 CANDIDATE ONLY

- Run ID: **40122845921**
- Base canonical SHA-256: `51249aad299ba874b4e688993aa1a4491cc5556cf6c3f0ede339504d672e0dcf`
- Candidate SHA-256: `e108b517924ceced165d356874b5e0a4598ec9a103d452f034ff4431ab34f9e0`
- Source T00-bis run: **40122469278**
- Candidate rows: **504**
- Base columns preserved string-for-string: **YES**
- BR-04 columns appended: **73**
- Strict BS closure from current SEC FSDS: **NOT DEMONSTRABLE**
- Leverage-threshold indeterminate rows: **211**
- `data/current/` modified: **NO**
- S2 regression: **NOT YET EXECUTED**
- S3 transport: **NOT YET EXECUTED**
- S4 engine test: **NOT YET EXECUTED**
- Blind Test: **NOT EXECUTED**

**`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.**

This file is staging evidence only and must not be treated as canonical until
S2, S3, S4, human approval, T31 and atomic promotion have all succeeded.
