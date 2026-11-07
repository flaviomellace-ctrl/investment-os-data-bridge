# DATA14 — current market refresh, research only

Main commit `2c6ba5809ab884c5daf0c1b0bd8f1bedb6bbf4c1` refreshed market data on 2026-10-26. Its canonical SHA-256 is `91b0f052957e6a0a34768cfb48838bafe9d2f7f589c3ad439f95c7178e6125e2`, replacing historical base `51249aad299ba874b4e688993aa1a4491cc5556cf6c3f0ede339504d672e0dcf`.

The refreshed DATA14 candidate is `bc47a98f342a69ecf6017937d7e713fb2733ab0de4057debe346fc268ccec0ea`. It changes exactly 1,506 cells from DATA12: price, market capitalization and retrieval timestamp for 502 rows. Row order, all non-market fields, every BR04 field and all 30 legacy amendments from DATA11/DATA12 are preserved. Other than these three fields, the old and new canonical inputs must match exactly. All three input hashes are pinned; a further main refresh fails closed and requires a new rebase.

Validation has two explicit scopes:

1. Historical DATA09 replay reconstructs the 212-column original canonical byte-for-byte from pinned S1 (including the original LF serialization). The new `--historical-base` option is explicit and DATA09-only; default S2 and transport still check live data/current against their approved base. Historical reports carry `base_scope=HISTORICAL_REPLAY`. Unit transport fixtures use this reproducible historical base, so their success/fault cases are independent of scheduled market updates.
2. DATA14 checks the current canonical hash, audits every changed cell, reconstructs the new candidate, requires a fresh passing historical fundamental regression, splits the new bytes, independently reassembles and verifies every chunk/range, and runs the hash-verified frozen engine on all 504 rows. It verifies both canonical and candidate bytes remain unchanged during execution. This is new market-rebase/transport/engine compatibility evidence, not transfer of old approvals or full economic validation of DATA14.

Historical replay never writes to data/current. The branch incorporates main's refreshed data/current tree unchanged; no market values are invented or regenerated. The research workflow now runs both scopes and cannot succeed merely by replaying the old candidate: the final current-base DATA14 gate is mandatory.

Run after DATA09, DATA11 and DATA12 reconstruction and a fresh DATA09 regression:

```
python src/regress_br04_candidate.py --research-data09 --historical-base
python src/br04_data14_market_refresh.py
```

`reconstruction.json` is deterministic custody metadata. The candidate, market ledger, chunks and runtime report are generated rather than committed. CI prints `DATA14_REPORT` with the new hash and aggregate results. No individual rankings or recommendations are produced. DATA13's finite fundamental gap counts remain applicable because all fields used by that screen are unchanged, but its receipt itself remains tied to DATA12.

Remaining source/economic gaps (including CEG annual SBC), independent R11/R12 and release validation are not closed. No promotion, LIVE, BUY/ADD or S6 dispatch.
