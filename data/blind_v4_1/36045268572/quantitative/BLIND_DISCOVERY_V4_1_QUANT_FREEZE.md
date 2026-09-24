# Investment OS V4.1 — Blind Discovery Quantitative Freeze

**QUANTITATIVE CANDIDATE SET FROZEN — DO NOT MODIFY**

- Frozen at UTC: **2026-09-24T19:02:45Z**
- GitHub Actions run: **36045268572**
- Workflow commit SHA: `ccbc19bc4034314fd297f32eb6fb60d7ed398367`
- Canonical fundamentals SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- Frozen V4.1 engine MD5: `68f626974592915d6c2a8e6583d6c77b`
- Universe: **504** companies
- Canonical columns: **285**
- Fresh market snapshot coverage: **99.6%** (502/504)
- Market-cap rule: **direct Nasdaq value only; never reconstructed from bridge share count**
- Validation material used by this workflow: **NO**
- Final Blind Test frozen: **NO — quantitative queue only; deep dives still pending**
- System status: **NOT LIVE**

## Pre-registered deterministic rules

1. BQS is computed before price/market cap is used.
2. Top-30 BQS eligibility: numeric BQS + `data_status=PRESENT` + bridge core data coverage >=70%.
3. Top-30 ordering: BQS descending, metric coverage descending, data coverage descending, ticker ascending.
4. IOS is attempted for every company allowed by the frozen V4.1 engine gate (BQS>=60 and bridge data coverage>=70), not only Top-30 BQS.
5. Top-20 IOS ordering: IOS descending, BQS descending, ticker ascending.
6. Deep-dive queue: first 10 names of that frozen IOS ordering. No discretionary substitution.
7. Every IOS with `ios_leverage_indeterminate=true` is labelled **PROVISIONAL** and cannot reach a trade Decision Gate without manual debt reconciliation.
8. BQS `PROVISIONAL` confidence is preserved; it is never silently upgraded.
9. Missing sector-specific data remain MISSING; no value is imputed as zero.

## Aggregate diagnostics

- BQS Top-30 eligible pool: **323**
- IOS numeric pool: **309**
- IOS with indeterminate leverage: **125**
- BQS confidence counts: `{"HIGH": 2, "NOT_CALCULATED": 6, "PROVISIONAL": 496}`
- IOS confidence counts: `{"CALCULATED": 2, "NOT_CALCULATED": 195, "PROVISIONAL": 307}`
- Module counts: `{"ASSETMGR_EXCH": 19, "BANK": 20, "GENERAL": 216, "INDUSTRIAL": 39, "INSURANCE": 29, "REIT": 30, "RESOURCES": 21, "SEMICONDUCTOR": 39, "SOFTWARE": 49, "UNKNOWN": 5, "UTILITY": 37}`

## Frozen Top 30 BQS

| Rank | Ticker | Name | BQS | Confidence | Metric cov. |
|---:|---|---|---:|---|---:|
| 1 | NEM | NEWMONT CORP | 98.5 | PROVISIONAL | 37.8% |
| 2 | MA | MASTERCARD INC A | 93.5 | PROVISIONAL | 70.4% |
| 3 | DXCM | DEXCOM INC | 92.8 | PROVISIONAL | 70.4% |
| 4 | ACGL | ARCH CAPITAL GROUP LTD | 92.3 | PROVISIONAL | 59.2% |
| 5 | MCO | MOODY S CORP | 92.2 | PROVISIONAL | 67.3% |
| 6 | RMD | RESMED INC | 92.1 | PROVISIONAL | 70.4% |
| 7 | FTNT | FORTINET INC | 91.9 | PROVISIONAL | 70.4% |
| 8 | ANET | ARISTA NETWORKS INC | 91.9 | PROVISIONAL | 67.3% |
| 9 | IDXX | IDEXX LABORATORIES INC | 91.7 | PROVISIONAL | 70.4% |
| 10 | META | META PLATFORMS INC CLASS A | 91.5 | PROVISIONAL | 70.4% |
| 11 | SPGI | S+P GLOBAL INC | 90.2 | PROVISIONAL | 70.4% |
| 12 | ISRG | INTUITIVE SURGICAL INC | 90.2 | PROVISIONAL | 67.3% |
| 13 | ADBE | ADOBE INC | 89.7 | PROVISIONAL | 70.4% |
| 14 | MNST | MONSTER BEVERAGE CORP | 89.1 | PROVISIONAL | 70.4% |
| 15 | TRV | TRAVELERS COS INC/THE | 88.9 | PROVISIONAL | 40.8% |
| 16 | MPWR | MONOLITHIC POWER SYSTEMS INC | 88.8 | PROVISIONAL | 63.3% |
| 17 | DECK | DECKERS OUTDOOR CORP | 88.6 | PROVISIONAL | 70.4% |
| 18 | TTD | TRADE DESK INC/THE CLASS A | 88.6 | PROVISIONAL | 70.4% |
| 19 | HWM | HOWMET AEROSPACE INC | 88.4 | PROVISIONAL | 60.2% |
| 20 | MSFT | MICROSOFT CORP | 88.3 | PROVISIONAL | 67.3% |
| 21 | APH | AMPHENOL CORP CL A | 88.2 | PROVISIONAL | 70.4% |
| 22 | FDS | FACTSET RESEARCH SYSTEMS INC | 88.2 | PROVISIONAL | 70.4% |
| 23 | INTU | INTUIT INC | 88.1 | PROVISIONAL | 70.4% |
| 24 | CDNS | CADENCE DESIGN SYS INC | 87.8 | PROVISIONAL | 70.4% |
| 25 | HOOD | ROBINHOOD MARKETS INC A | 87.6 | PROVISIONAL | 60.2% |
| 26 | PTC | PTC INC | 87.3 | PROVISIONAL | 70.4% |
| 27 | MSI | MOTOROLA SOLUTIONS INC | 87.1 | PROVISIONAL | 66.3% |
| 28 | PGR | PROGRESSIVE CORP | 87.0 | PROVISIONAL | 52.0% |
| 29 | APO | APOLLO GLOBAL MANAGEMENT INC | 86.9 | PROVISIONAL | 60.2% |
| 30 | VRSN | VERISIGN INC | 86.4 | PROVISIONAL | 70.4% |

## Frozen Top 20 IOS

| Rank | Ticker | Name | IOS | BQS | IOS confidence |
|---:|---|---|---:|---:|---|
| 1 | DECK | DECKERS OUTDOOR CORP | 98.3 | 88.6 | PROVISIONAL |
| 2 | FISV | FISERV INC | 96.9 | 79.3 | PROVISIONAL |
| 3 | CMCSA | COMCAST CORP CLASS A | 96.4 | 76.2 | PROVISIONAL |
| 4 | FOX | FOX CORP CLASS B | 96.1 | 78.9 | PROVISIONAL |
| 5 | DAL | DELTA AIR LINES INC | 95.7 | 71.3 | PROVISIONAL |
| 6 | APA | APA CORP | 95.5 | 69.7 | PROVISIONAL |
| 7 | GM | GENERAL MOTORS CO | 95.3 | 68.6 | PROVISIONAL |
| 8 | ADBE | ADOBE INC | 95.2 | 89.7 | PROVISIONAL |
| 9 | TROW | T ROWE PRICE GROUP INC | 95.0 | 73.2 | PROVISIONAL |
| 10 | AMP | AMERIPRISE FINANCIAL INC | 94.8 | 90.2 | PROVISIONAL |
| 11 | CHTR | CHARTER COMMUNICATIONS INC A | 94.6 | 63.9 | PROVISIONAL |
| 12 | MGM | MGM RESORTS INTERNATIONAL | 94.5 | 63.3 | PROVISIONAL |
| 13 | GDDY | GODADDY INC CLASS A | 94.4 | 83.2 | PROVISIONAL |
| 14 | APTV | APTIV PLC | 94.2 | 61.4 | PROVISIONAL |
| 15 | VZ | VERIZON COMMUNICATIONS INC | 94.1 | 60.5 | PROVISIONAL |
| 16 | URI | UNITED RENTALS INC | 93.3 | 84.6 | PROVISIONAL |
| 17 | PYPL | PAYPAL HOLDINGS INC | 93.3 | 81.8 | PROVISIONAL |
| 18 | LULU | LULULEMON ATHLETICA INC | 93.1 | 83.8 | PROVISIONAL |
| 19 | EXPE | EXPEDIA GROUP INC | 92.2 | 77.8 | PROVISIONAL |
| 20 | FOXA | FOX CORP CLASS A | 91.8 | 78.9 | PROVISIONAL |

## Frozen Deep-Dive Queue (max 10)

| Queue | Ticker | Name | IOS | BQS | Caveat |
|---:|---|---|---:|---:|---|
| 1 | DECK | DECKERS OUTDOOR CORP | 98.3 | 88.6 | BQS_PROVISIONAL |
| 2 | FISV | FISERV INC | 96.9 | 79.3 | BQS_PROVISIONAL |
| 3 | CMCSA | COMCAST CORP CLASS A | 96.4 | 76.2 | BQS_PROVISIONAL|LEVERAGE_THRESHOLD_INDETERMINATE |
| 4 | FOX | FOX CORP CLASS B | 96.1 | 78.9 | BQS_PROVISIONAL|LEVERAGE_THRESHOLD_INDETERMINATE |
| 5 | DAL | DELTA AIR LINES INC | 95.7 | 71.3 | BQS_PROVISIONAL|LEVERAGE_THRESHOLD_INDETERMINATE |
| 6 | APA | APA CORP | 95.5 | 69.7 | BQS_PROVISIONAL |
| 7 | GM | GENERAL MOTORS CO | 95.3 | 68.6 | BQS_PROVISIONAL|LEVERAGE_THRESHOLD_INDETERMINATE |
| 8 | ADBE | ADOBE INC | 95.2 | 89.7 | BQS_PROVISIONAL |
| 9 | TROW | T ROWE PRICE GROUP INC | 95.0 | 73.2 | BQS_PROVISIONAL |
| 10 | AMP | AMERIPRISE FINANCIAL INC | 94.8 | 90.2 | BQS_PROVISIONAL|LEVERAGE_THRESHOLD_INDETERMINATE |

## Stop condition

This package freezes only the quantitative discovery and the deep-dive queue.
Do not open or use any validation set yet.
The next stage may research only the companies in `V4_1_DEEP_DIVE_QUEUE.csv`, using a uniform template.
After those deep dives and any required independent Decision Gates are finished, the final Blind Discovery result must be frozen before validation.
