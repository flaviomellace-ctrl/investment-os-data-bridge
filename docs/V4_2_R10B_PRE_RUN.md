# V4.2 R10B — Primary-source recovery contract

R10A audited all 150 previously numeric rows blocked by V4.2.

Results:
- deterministic repair candidates from existing canonical facts: **0**
- rows requiring primary-source recovery: **136**
- rows with economically non-computable series: **31**
- unexplained rows: **0**

Therefore R10B is a source-recovery exercise, not a scoring-model change.

## Source

Only **SEC Companyfacts** is used in R10B, with the same declared `SEC_CONTACT_EMAIL`
User-Agent discipline already used by the Data Bridge.

## Pre-registered extraction rules

- no ticker whitelist;
- no fuzzy XBRL concept matching;
- annual forms only: 10-K / 20-F / 40-F;
- exact target fiscal-period end;
- annual-duration facts only (250–450 days);
- only the concept allowlist embedded in `r10b_primary_source_recovery.py`;
- latest filed admissible fact wins within a concept;
- existing canonical values are never overwritten;
- every recovered direct fact receives source URL, taxonomy, concept, unit, accession,
  filing date, form, start/end and duration provenance;
- MISSING remains MISSING if no admissible fact exists.

The candidate is written under `data/v4_2/r10b/<run_id>/`.
`data/current` is immutable.

## Derived fields allowed after primary recovery

Only deterministic recomputation from recovered + existing primary facts:
- revenue CAGR3;
- diluted-shares YoY;
- FCF/share CAGR3;
- FCF CAGR3;
- annual FCF;
- SBC/revenue.

No BQS or IOS is calculated in R10B.

## Next gate

R10C may run the **same frozen V4.2 engine** on the frozen R10B candidate.
No model tuning is authorized from R10/R10A/R10B results.

**System remains NOT LIVE.**
