# V4.2 R8/R9 — PRE-RUN PACKAGE

- Data: **2026-09-25**
- Status: **READY TO RUN**
- System: **NOT LIVE**
- Real-data V4.2 ranking: **NOT AUTHORIZED / NOT RUN**

## Frozen references bundled

`src/investment_os/v4_1_frozen/v4_scoring.py`
- MD5: `68f626974592915d6c2a8e6583d6c77b`
- SHA-256: `91ce6231e8070a6fea10d2f025d3d60256ee418ff5ddeedd0215198171c13fc9`

`tests/v4_1_frozen/test_v4.py`
- SHA-256: `4c095a89db80b8206760f8f7c4cc817abfa1b72a14743b58f51c9c0aa38101b1`

These are immutable V4.1 reference copies for regression only.

## R8

R8 verifies:
- GENERAL/SOFTWARE/MARKETPLACE -> IOS_GENERAL;
- BANK/ASSETMGR -> IOS_BANK;
- INSURANCE -> IOS_INSURANCE;
- REIT -> IOS_REIT;
- marketplace economics remain volume-based;
- marketplace discount-rate risk premium remains;
- bank cannot fall back to OCF valuation;
- insurance requires combined ratio;
- REIT requires AFFO.

## R9

R9 runs only inside the checked-out repository and validates actual `data/current`:

- canonical SHA `d2207e92...`;
- 504 rows;
- 285 columns;
- 50 chunks;
- per-chunk SHA;
- row-range contiguity;
- hard byte cap;
- common header;
- exact byte reassembly;
- manifest S7/T20 state;
- direct market-cap invariant from the frozen blind receipt.

It does **not** calculate a V4.2 BQS/IOS ranking.

## Workflow

Upload `.github/workflows/v4-2-r8-r9-regression.yml`, then run it manually.
On PASS it commits four evidence files under `docs/`.

**No engine integration and no real ranking before R8/R9 PASS.**
