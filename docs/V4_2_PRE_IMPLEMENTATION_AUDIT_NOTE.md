# V4.2 PRE-IMPLEMENTATION AUDIT NOTE

## Key correction to the post-blind diagnosis

The V4.1 engine **already contains** a `MARKETPLACE_NETWORK` module.

This is visible directly in the frozen `v4_scoring.py`:
- `MODULES` includes `MARKETPLACE_NETWORK`;
- `economics_spec("MARKETPLACE_NETWORK")` uses `ebitda_on_volume`, `fcf_on_volume`, `take_rate`, `cash_conversion`;
- `moat_spec("MARKETPLACE_NETWORK")` adds `two_sided_growth`, `retention`, `unit_cost_decline`, `frequency_growth`;
- the regression suite already has the marketplace gross/net presentation invariance test.

The real-data adapter/preflight, however, classifies modules by SIC. Its `module_of(sic)` routes SIC 737x to `SOFTWARE` and has no route to `MARKETPLACE_NETWORK`.

Earlier BR-09 design work had already identified this exact structural gap:
- SIC cannot reliably identify digital marketplace/network economics;
- marketplace KPI are mostly narrative/non-XBRL;
- documentary classification and enrichment are required before BQS.

Therefore the V4.1 validation FAIL remains valid, but the engineering diagnosis is more precise:

> V4.1 did not fail because the marketplace module was absent from the scoring engine.  
> It failed because the real-data pipeline never activated that existing module for the relevant companies.

## Second correction: IOS formula traceability

The IOS formula is present in the frozen engine source. What was missing from the clean-room validation package was **direct exposure of the exact formula/version and per-ticker rows**, forcing the validator to infer parts of it.

V4.2 should therefore fix **freeze traceability**, not pretend that the IOS formula never existed.

## Consequence for V4.2

Do not redesign `MARKETPLACE_NETWORK` from scratch.

Priority order:
1. activate BR-09 classification/enrichment;
2. freeze/audit the routing evidence;
3. add a separate inflection discovery lane without weakening valuation discipline;
4. only then test whether any IOS growth formula change is still necessary.

**System remains NOT LIVE.**
