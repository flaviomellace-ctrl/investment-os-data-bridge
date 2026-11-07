# DATA10 — read-only inventory on DATA09

This is a gap inventory, not a new candidate or a release approval. Candidate
9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d remains unchanged.
Reproduce after DATA09 reconstruction with `python src/br04_data10_inventory.py`.

The finite screen identifies 380 rows with at least one listed open item. All
504 rows remain BUY/ADD blocked, including 124 without one of these listed flags.
Counts overlap and are not percentages of project completion. Existing economic
case, ROSCA and IP row-basis blocks are carried forward, not independently closed.

The old RC1 ledger and primary proof bundle match the hashes in its original
receipt. For MCD, CEG and WELL, the same annual filings remain in DATA09. Their
old amendments differ in 31 strings: five are numerically equivalent formatting,
and 26 require substantive review (MCD 5, CEG 10, WELL 11). No old amendment is
silently applied to the newer base. CEG/WELL's total-revenue convention remains a
development proposal requiring explicit reconciliation, not an approved policy.

MCD is the next concrete repair: four share-count observations remain in millions
(716.4 / 721.9 / 721.9 / 732.3) while FY-minus-3 is in absolute shares. This makes
the per-share CAGR inconsistent. Archived table-caption evidence requires unit
normalization and recomputation; unchanged share-growth ratios must not be
artificially changed just for floating-point formatting. Implement as a separate
scoped amendment with new custody and validation, since it alters legacy fields.

The earlier PH precision evidence belongs to an older annual filing and cannot be
automatically transferred. No new SEC authentication, independent review, funding
closure, economic clearance, promotion or LIVE status is claimed by this screen.
