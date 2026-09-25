# V4.2 R8/R9 — SECTOR VARIANT & TRANSPORT REGRESSION

- Status: **PASS**
- System: **NOT LIVE**
- V4.2 real-data ranking executed: **NO**
- V4.1 modified: **NO**
- Frozen V4.1 engine MD5: `68f626974592915d6c2a8e6583d6c77b`
- Canonical SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- Rows / columns: **504 / 285**
- Chunks: **50**
- Reassembled SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`

## R8

- Frozen V4.1 regression: **PASS**
- Sector-variant regression: **PASS**
- R8 PASS lines: **21**
- R8 FAIL lines: **0**

## R9

Validated against actual `data/current` without calculating rankings:

- canonical SHA;
- 504 rows / 285 columns;
- 50 chunk declarations;
- every chunk SHA;
- hard byte cap;
- common header;
- contiguous row ranges;
- `data/current` URLs;
- byte-identical reassembly;
- reassembled SHA;
- manifest S7_VERIFIED / T20 status;
- frozen blind receipt direct-market-cap invariant;
- no blank/duplicate ticker.

## Failed checks

- none

## Conclusion

**R8/R9 PASS. Engine integration may proceed, but no real ranking is authorized until the integrated V4.2 engine/adapters are frozen.**
