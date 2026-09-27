# V4.2 R10E — Evidence and provenance reconciliation

Date: 2026-09-27. Status: technical evidence collection; NOT LIVE.

## Scope

R10D run 36303846263 completed successfully, with nine R6/R7 review cases and seven missing leverage diagnostics. A successful execution does not resolve those findings.

R10E preserves the frozen queue, rankings, economic modules and R10D outputs. It collects primary evidence for the existing queue only. It does not emit BUY/ADD, change thresholds, normalize earnings, declare commitments immaterial, or clear any substantive gate.

## Findings before collection

- R10D searches keywords without interpreting negation, materiality or accounting context. No keyword hit is not evidence that a condition is absent.
- R10D does not retain the fact used for D&A with its annual duration. R10E selects only facts with the exact frozen accession and period, USD unit, annual form and 330–380-day duration. Conflicting values remain unresolved.
- The candidate period for Adobe is 2025-11-30, while R10D reports 2025-11-28 from the same accession. R10E records both dates; any alternative facts remain review proposals.
- FOX's frozen fundamentals use the 2025 annual filing, while R10D's overlay uses the 2026 filing. Both sources are retained separately.
- The frozen rows contain MISSING or PARTIAL debt. A finite numeric value cannot by itself establish that debt is complete.
- A zero quantified commitments total cannot establish that the company has no commitments. Lease overlap with debt requires explicit reconciliation.

These findings concern transport and evidence completeness, not changes to frozen economics. Names appear here only to document observed data issues; no ticker-dependent logic is introduced.

## Outputs and integrity

- Verify SHA-256 of the frozen candidate CSV, R10D queue/overlays and R6/R7 module before requests.
- Retrieve the pinned filings and verify the original R10D filing byte hashes.
- Preserve source URLs, hashes, accession, periods, excerpts and same-accession XBRL fact inventory in one dossier per entity.
- Preserve full fetched SEC documents in the Actions artifact for 90 days; repository dossiers and manifest are durable.
- Record source hashes before and after collection, and reject a mutation.
- Do not overwrite evidence on a workflow rerun: run ID and attempt identify each output directory.
- A failed retrieval or seal check is not a successful collection; partial diagnostics may be available in the workflow artifact.
- Current Companyfacts downloads are supplementary evidence, not a representation of a historical archive.

## Tests

Synthetic tests cover annual versus quarterly selection, accession isolation, conflicting values, zero versus missing, period mismatch and retention of negated lexical contexts. No real ticker appears in selection logic or tests.

## Gates still required

Semantic cash-quality and commitments review remains OPEN until quantified and sourced, including debt/lease overlap and period alignment. R11 requires separately sealed non-current controls with pre-registered scoring. R12 requires a clean-room executor that has not seen the development conversation or target validation. Existing V4_2_REGRESSION_PLAN.md acceptance criteria continue to apply.

Collection completion is not validation completion and does not establish project completion at 100%.
