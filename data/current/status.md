# Investment OS Data Bridge — stato

Aggiornato: **2026-09-24T10:58:20Z**

- Righe universo equity-like: **504**
- Ticker con CIK SEC mappato: **99.8%**
- Società con filing annuale individuato: **100.0%**
- Società con >=90% core metric coverage: **64.1%**
- Ultimo SEC Financial Statement Data Set disponibile: **2026Q2**
- Fondamentali costruiti usando trimestri: **2025Q3, 2025Q4, 2026Q1, 2026Q2**

## Importante

La copertura qui è una misura tecnica, non un BQS. Metriche non appropriate a un settore possono essere `NOT_APPLICABLE` nel successivo processo di analisi. Prima di BUY/ADD i finalisti devono essere verificati contro gli ultimi filing e fonti primarie.
## V4.1 enrichment BR-01 / BR-02

- SEC quarterly datasets usati per lo storico: **16** (2022Q3 → 2026Q2)
- Storico ricavi a 4 esercizi: **85.7%**
- Storico operating income a 4 esercizi: **71.4%**
- Storico FCF a 4 esercizi: **78.0%**
- Storico diluted shares a 4 esercizi: **70.6%**
- SBC corrente disponibile: **80.0%**
- Revenue CAGR 3y calcolabile: **85.5%**
- Operating-income CAGR 3y calcolabile: **62.5%**
- FCF CAGR 3y calcolabile: **64.3%**
- FCF/share CAGR 3y calcolabile: **47.4%**

`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
## V4.1 enrichment BR-03

- SEC quarterly datasets usati: **16** (2022Q3 → 2026Q2)
- `annual_buyback` disponibile: **81.2%**
- `annual_dividends_paid` disponibile: **78.2%**
- `buyback_accretion` disponibile/N.A.: **67.5%**
- `payout_ratio` disponibile: **74.2%**
- `BUYBACK_TAG_ABSENT_CF_PRESENT`: **17.5%**
- `DIVIDENDS_TAG_ABSENT_CF_PRESENT`: **20.4%**
- `NO_BUYBACK_NO_SBC`: **0**
- `PAYOUT_NEGATIVE_EARNINGS`: **27**
- `SHARE_COUNT_DISCONTINUITY`: **10**
- Buyback tag usage: **{"PaymentsForRepurchaseOfCommonStock": 395, "PaymentsForRepurchaseOfEquity": 7, "TreasuryStockValueAcquiredCostMethod": 7}**
- Dividend tag usage: **{"PaymentsOfDividends": 138, "PaymentsOfDividendsCommonStock": 236, "PaymentsOfOrdinaryDividends": 20}**
- Bridge regression checks: **16/16 passed**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
## V4.1 enrichment BR-05

- Fonte primaria market data: **Nasdaq public stock screener**
- Fallback: **FMP stable single-symbol quote, solo per righe mancanti/incomplete**
- Prezzo + market cap direttamente disponibili: **99.6%**
- Market cap ricostruita da bridge shares: **NO**
- `MISSING` resta `MISSING`: nessuna assenza è convertita in zero.
- Source counts: **{"MISSING": 2, "NASDAQ_PUBLIC_SCREENER": 502}**


## V4.1 enrichment BR-04 — PROMOTED

- Base canonical SHA-256: `c95e356632182dddd85b002a552eefa83da27264838617d8661af895fbb69594`
- Promoted candidate SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- S1 candidate run: **35977079536**
- S2 regression run: **35980033396** — PASS
- S3 transport run: **35981763317** — BR04-T20 PASS
- S4 engine preflight run: **35985072617** — BR04-T18 PASS
- S6 / BR04-T31 run: **35989098494** — PASS
- Human approval recorded: **2026-09-24T10:31:00Z**
- Frozen V4.1 engine MD5: `68f626974592915d6c2a8e6583d6c77b`
- Candidate rows: **504**
- Candidate columns: **285**
- Transport chunks: **50**
- `LEVERAGE_THRESHOLD_INDETERMINATE`: **193**
- `CUSTOM_TAG_DEBT_BY_LABEL`: **45**
- `TOTAL_DEBT_BELOW_LEGACY`: **2**
- Previous canonical archived at: `data/archive/20260924T104550Z`
- `data/current/sp500_fundamentals.csv` promoted: **YES**
- Blind Test: **NOT EXECUTED**

**`MISSING` resta `MISSING`: nessuna assenza è convertita in zero.**


## BR-04 S7 — POST-PROMOTION VERIFIED

- S7 run: **35989832022**
- Verified at: **2026-09-24T10:53:29Z**
- Canonical SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- Approved candidate SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- Canonical hash equals approved candidate: **YES**
- BR04-T20 on canonical: **PASS**
- Parts verified: **50/50**
- Rows verified: **504/504**
- Reassembled canonical byte-identical: **YES**
- Pre-promotion archive verified: **YES**
- BR-04 staging/promotion lifecycle: **CLOSED**
- Blind Test: **NOT EXECUTED**

## BR-04 S7 — METADATA FINALIZED

- Finalization run: **35990281570**
- Finalized at: **2026-09-24T10:58:20Z**
- Transport URLs point to: `data/current/`
- `fundamentals_chunks.json` canonical URLs: **YES**
- `fundamentals_chunks.md` canonical URLs: **YES**
- Manifest output hashes refreshed: **YES**
- Canonical fundamentals SHA-256 unchanged: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- BR04-T20 re-verified after metadata finalization: **PASS**
- Blind Test: **NOT EXECUTED**
