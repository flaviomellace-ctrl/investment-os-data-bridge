# V4.2 ENGINE INTEGRATION SPEC — PRE-REAL-DATA

- Data: **2026-09-25**
- Stato: **INTEGRATION CANDIDATE — NOT YET FROZEN IN REPOSITORY**
- Sistema: **NOT LIVE**
- V4.1 engine MD5 reference: `68f626974592915d6c2a8e6583d6c77b`
- V4.2 candidate engine MD5: `232ac18be2ada2d3a6ef97b0d4308b7b`
- V4.2 candidate engine SHA-256: `cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e`

## Authorized numeric changes

### 1. BQS

**No change.**

All BQS components, weights, anchors, module specifications and confidence logic remain identical to V4.1.

### 2. IOS_GENERAL growth

V4.1 used revenue CAGR as the growth signal and capped the expected-return growth contribution at 10%.

V4.2 uses the pre-registered G2 policy:

`g = min(max(revenue_cagr3,0), max(fcf_per_share_cagr3,0), 15%)`

Rules:
- both inputs are required;
- MISSING/CONFLICTING is not converted to zero;
- expected-return growth contribution can be at most 15%;
- DCF first-stage growth remains capped at **12%**, preserving the prudential V4.1 valuation cap;
- bear/base/bull structure remains unchanged apart from using the guarded growth input.

### 3. Owner earnings input integrity

For IOS_GENERAL, all are now required:
- OCF;
- capex;
- SBC.

If any is MISSING/CONFLICTING, IOS is not calculated.

This removes the V4.1 Python fallback `(capex or 0)` / `(sbc or 0)`.

### 4. Dilution integrity

`share_change` is now a required IOS input for GENERAL, BANK, INSURANCE and REIT.

Missing dilution is not assumed to be zero.

### 5. Market cap conflict handling

`None`, `0`, `NOT_APPLICABLE` or `CONFLICTING` market cap blocks IOS.

Direct-source market cap remains mandatory.

## Unchanged

- IOS weights 30/25/20/15/10;
- BQS gate >=60;
- coverage gate >=70;
- BANK / ASSETMGR / INSURANCE / REIT valuation formulas;
- discount-rate structure;
- optionality = 0 points;
- can_emit_buy rules;
- system remains NOT LIVE.

## Modules outside numeric scoring

These remain separate pre-scoring / post-scoring layers:
- BR-09 marketplace classifier;
- Lane I Economic Inflection;
- cash-quality diagnostics;
- commitments gate;
- leverage stress view.

They are not folded into BQS weights.

## No-real-data rule

No V4.2 real-company ranking is authorized until:
1. this candidate is uploaded;
2. synthetic integration workflow passes;
3. engine/module hashes are frozen in an engine manifest.

**END**
