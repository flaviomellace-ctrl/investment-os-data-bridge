# V4.2 R10E — Reconciliation evidence

Evidence collection only; all substantive cases remain OPEN. System NOT LIVE.

| Entity | Missing frozen leverage inputs | Additional integrity issues |
|---|---|---|
| FISV | None; debt completeness still requires review | DEBT_PARTIAL |
| CMCSA | None; debt completeness still requires review | DEBT_PARTIAL |
| FOX | annual_operating_income, cash_and_equivalents | R10D_OVERLAY_USES_DIFFERENT_FILING_FROM_FROZEN_FUNDAMENTALS, DEBT_PARTIAL |
| GM | total_debt | DEBT_MISSING |
| ADBE | annual_DA_exact_frozen_period | CANDIDATE_PERIOD_DIFFERS_FROM_SAME_ACCESSION_REPORT_DATE, DEBT_PARTIAL |
| TROW | total_debt, annual_DA_exact_frozen_period | DEBT_MISSING |
| AMP | annual_operating_income, total_debt, cash_and_equivalents | DEBT_MISSING |
| NEM | annual_operating_income | DEBT_PARTIAL |
| FIX | None; debt completeness still requires review | DEBT_PARTIAL |
| ANET | total_debt | DEBT_MISSING |

## Interpretation

- A lexical match is a review lead; it does not establish materiality, direction, amount or negation.
- No match is NOT_ESTABLISHED, not a verified negative. Contexts may be truncated; inspect the full primary document.
- Zero quantified commitments in R10D is not proof of zero obligations.
- PARTIAL debt is not promoted to a complete leverage measure.
- Facts at the actual report date are review proposals only; no frozen input, score, threshold, queue or gate is overwritten.
- Annual facts must match accession, end date, unit and a 330–380-day duration. Conflicting values remain CONFLICTING.
- Current Companyfacts retrieval is new evidence. It is not represented as a historical point-in-time archive.
- Full downloaded primary sources are preserved in the workflow artifact; repository dossiers retain hashes, source URLs, contexts and fact provenance.

## Remaining required gates

1. Document and reconcile cash, commitments, leases/debt overlap and missing inputs.
2. R11: use separately sealed non-current controls with pre-registered scoring.
3. R12: clean-room executor receives only frozen artifacts and safe methodology, not this conversation or target validation.
4. Bootstrap/IPS only after the existing regression plan's acceptance criteria are satisfied.

A successful workflow means evidence collection completed, not validation passed or project 100% complete.
