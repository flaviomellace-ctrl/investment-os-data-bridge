# V4.2 R10D — Technical Fix 1: dynamic dataclass module import

R10D run `36269101027` failed before any SEC evidence scan.

## Root cause

The generic dynamic loader used `importlib.util.module_from_spec(...)` followed by
`exec_module(...)` without registering the module in `sys.modules`.

Under Python 3.12, modules defining `@dataclass` objects can fail inside the standard
library's dataclass processing when loaded this way, because the module is absent from
`sys.modules`.

The failure occurred while loading `src/marketplace_classifier_v42.py`.

## Fix

The R10D loader now registers the dynamic module in `sys.modules` before executing it.

A dedicated regression test loads both:
- `marketplace_classifier_v42.py`
- `cash_quality_commitments_v42.py`

through the same R10D loader.

The workflow also has a path-scoped `push` trigger. Once these files are uploaded,
the upload commit itself should start R10D automatically; evidence commits under
`data/v4_2/r10d/**` do not match the trigger and therefore do not recurse.

No BQS, IOS, G2, BR-09 economic rule, R6/R7 threshold, Lane-I rule, ranking rule,
or validation material was changed.

**System remains NOT LIVE.**
