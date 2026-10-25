# DATA09 — selective rebase onto S1 40122845921

Research only. No promotion, LIVE, economic clearance, or BUY/ADD permission.

The old DATA07 candidate was fully reconstructed from the archived, hash-pinned
DATA02–07 source chain; its SHA-256 is 2ce0e525cdff6faa8d2051b9982aad8505ade199611c469a162605be53af0ef8.
This is verification of archived copies, not a new SEC authentication or an
independent review. The compact primary_evidence.json records the source hashes,
filing contexts, debt and cash reconciliations and DATA08 balance-sheet bridge.
Source archive: ChatGPT Library V43_DATA_07_CASSA_CVX_RICONCILIATA_20261022.zip,
libfile_a2922a6428e08191b66e1e1de51d2ee6; DATA08 archive
libfile_4d999145d9348191b60d6f7a35520806.

## Changes and dependency findings

The initial comparison identified 55 final DATA04–07 cells. They depend on 18
lease cells recovered in DATA02, which are also absent from the new S1. MET's
old prudential exact ratio must additionally be blanked and its indeterminate
flag set: the named partial debt subtotal does not prove exact net cash.
Total: 75 changed cells, five rows. Lease-missing flags are removed only where
supported facts are restored. Debt remains PARTIAL for all five companies.

All 212 preexisting columns and all 499 other rows are preserved. Current source
quarters remain 2022Q4:2026Q3. The three banks retain the accepted builder's
NOT_APPLICABLE leverage convention and false numerical indeterminate flag;
BANK_FUNDING_PERIMETER_UNRESOLVED explicitly retains their separate scope block.
The older DATA07 bank booleans are deliberately not transplanted. Numerical
indeterminate rows rise from 211 to 212, due to MET only.

The full CVX balance-sheet equality in DATA08 is not debt-perimeter closure:
bs_closure_residual_pct is preserved, and no closure is asserted.

## Reproduction

From repository root:

    python src/rebase_br04_data09.py --input data/staging/br04/40122845921/candidate/sp500_fundamentals.csv
    python -m unittest discover -s tests -p 'test_br04_data09_rebase.py' -v

The script writes only data/research/br04-data09/RESEARCH_NOT_PROMOTED.csv and
reconstruction.json. The CSV is reproducible and is not checked in. Input bytes
and the 75-cell manifest are SHA-256 pinned. Expected output SHA-256:
a07152b3156b4dcfed065db3fe613a919604d4093084275c530d533695996449.

Local validation: exact deterministic reconstruction; four test methods including
five semantic rejection cases; input/manifest tamper rejection; all legacy cells
and all other rows unchanged. Result: 480 PARTIAL, 24 MISSING, zero CONFLICTING.
This resolves five mapping conflicts, not all missing data or economic cases.

## Remaining validation

The new hash has NOT passed the complete S2, S3 or S4 workflows. Existing evidence
for e108b517...f9e0 is not transferable. Source-component audit reconciliation
must accompany the added source facts before those workflows can approve this
candidate. No numeric staging directory is created, so the automatic selection
of the S1–S4 pipeline cannot pick DATA09. Do not dispatch S6.

## Primary-component supplement

Run `python src/audit_br04_data09.py` after reconstruction. The hash-pinned
primary_component_links.json reconciles 20 aggregates to 28 archived facts,
including filing/period/unit identity, debt coverage disjointness, component
strings and lease present-value equations. Each link explicitly supersedes the
corresponding S1 used_as role for that ticker; the original S1 audit remains
unchanged. These are primary XBRL facts, not assertions of FSDS face membership.

Seven negative semantic cases test wrong accession, period, unit, value,
overlapping debt coverage, asset-as-debt classification and lease PV mismatch;
byte tampering of candidate or primary evidence also fails closed.

Full S2 integration remains pending: source_validation currently verifies selected
components against SEC FSDS NUM and face tables. It must explicitly distinguish
and validate the primary-document supplement, while preserving all unamended FSDS
checks. Copying these links into br04_components.csv and labelling them FSDS would
misrepresent their origin. S3/S4 have not been run on the DATA09 hash.
