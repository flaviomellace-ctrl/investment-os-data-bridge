# V4.2 R10C — PRE-RUN

R10B run `36268043494` is the first successful primary-source recovery:

- 136 queue companies;
- 98 rows touched;
- 244 direct SEC facts recovered;
- 167 deterministic derived fields recovered;
- 411 provenance rows;
- 105 unresolved items;
- 0 fetch failures.

Candidate SHA-256:
`979914c918cdd5771409bca679ce8e84f3224bb602ed36c0e1dcfb71fbd920c6`

R10C reruns the **same frozen V4.2 engine** on that candidate.

It freezes module routing to R10 and freezes market price/capitalization to the original
R10 snapshot. It recomputes BQS and IOS because recovered facts legitimately improve
inputs used by those frozen formulas.

No model parameter, threshold, weight, G2 rule, Lane-I rule or 7+3 rule may change.

R10C is a recovery-impact measurement, not a new blind validation.

**System remains NOT LIVE.**
