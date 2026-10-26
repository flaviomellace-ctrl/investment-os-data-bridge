# DATA11 — MCD share units, research only

Input is the exact DATA09 candidate, SHA-256 `9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d`.
Output is `c856d8af683e1b4ca8d21ba3c8258b7a19714301964209f9176893728a33b486`.

Four MCD share fields are normalized using the explicit annual statement caption “In millions, except per share data”. The already normalized FY2022 value is preserved. FCF/share CAGR is recomputed from current OCF, capex and shares: 0.10658225297861201 (10.6582%). Share-change ratios keep their existing equivalent precision. Exactly five legacy cells change; all other 503 rows and all BR04 fields remain unchanged.

`amendment.json` records the five changes and input/output identities. `archive_verification.json` records a local re-read of every receipt-listed source with hash and size checks, followed by matching each of the five MCD proofs against the extracted instance and scoped inline table. This is archived evidence, not a fresh SEC fetch. The source receipt is pinned; the DATA10 proof bundle is unchanged. The archived raw source bundle is not duplicated here.

Reproduce after DATA09 reconstruction:

```
python src/br04_data11_mcd.py
python src/br04_data09_runtime.py
python src/br04_data11_engine.py
```

For an independent archive re-read (requires lxml), supply the exact receipt-listed archive directory with `--archive PATH`. The archive contains PRIMARY_RECEIPT.json and its raw inventory.

The candidate CSV is generated, not committed. The compatibility report processes all 504 rows with the frozen engine and emits aggregates only. It is not new S2/S3/S4 approval: DATA09's legacy-preservation contract cannot transfer to these amended legacy fields. No promotion, economic clearance, independent R11/R12, or BUY/ADD authorization. CEG/WELL revenue-policy decisions remain open.
