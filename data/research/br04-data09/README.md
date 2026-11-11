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
9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d.

Local validation: exact deterministic reconstruction; four test methods including
five semantic rejection cases; input/manifest tamper rejection; all legacy cells
and all other rows unchanged. Result: 480 PARTIAL, 24 MISSING, zero CONFLICTING.
This resolves five mapping conflicts, not all missing data or economic cases.

## Remaining validation

The research S2 extension is implemented below; its remote result is recorded
separately. Research S3/S4 are implemented and locally verified below. Existing approvals for the
original S1 are not transferable. No numeric staging directory is created;
promotion workflows cannot select DATA09. Do not dispatch S6.

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

## Research S2 integration (explicit opt-in)

`python src/regress_br04_candidate.py --research-data09` now reconstructs DATA09
and validates its primary evidence before applying the regression suite. Default
S1 behavior is unchanged. Research outputs stay outside numeric staging and use
a distinct `S2_RESEARCH` phase/schema with original_fsds_contract_approval=false.

The in-memory component view preserves 3,937 FSDS rows, supersedes six incorrect
associations and adds 28 primary links. JPM's 1,493,429m loans asset is explicitly
reclassified from CUSTOM_DEBT to CUSTOM_NON_DEBT using its pinned asset evidence;
the original audit and every source staging file are retained unchanged.

T11 gains a hash-pinned primary-XBRL path. T24 still independently requires SEC
PRE balance-sheet face membership for all total-debt components; primary rows
are matched by filing, BS, tag and taxonomy version because they have no PRE line
number. No absence is waived. The PR workflow downloads SEC quarters and records
all 29 tests and three blocking gates against the new candidate hash.

The five amended rows now carry PRIMARY_DOCUMENT_SUPPLEMENTED instead of
FSDS_FACE_ONLY, making their mixed provenance explicit. This changes the output
hash from a07152b3... to 9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d;
the edit count remains 75. Results for the previous hash do not transfer.

## Research S3/S4 transport and frozen-engine preflight

After reconstruction:

    python src/br04_data09_runtime.py
    python data/research/br04-data09/runtime/test_v4.py
    python src/br04_data09_transport.py
    python src/br04_data09_preflight.py

The runtime loader pins the archived successful S2 receipt and restores the
frozen engine and synthetic tests from the existing S4 workflow. Both decoded
files are SHA-256 checked; engine MD5 remains 68f626974592915d6c2a8e6583d6c77b.
The S3 runner uses the existing production splitter; S4 independently checks part
hashes, ranges, headers, byte identity and candidate custody before evaluating
all rows with the original derivation and frozen engine. Reports have distinct
S3_RESEARCH/S4_RESEARCH phases and original_fsds_contract_approval=false.
All output stays in this research directory. No S1 staging metadata is invented.

Local pipeline: 50 parts, 504 rows, 285 columns, zero engine exceptions; original
canonical and candidate bytes preserved. Seven integration tests cover successful
execution and rejection of altered canonical data, candidate, S2 receipt, chunk,
engine or row ranges. The PR workflow repeats these checks remotely after S2.
This technical preflight does not close missing data, economic cases, independent
reviews or funding perimeters, and does not authorize BUY/ADD or promotion.
