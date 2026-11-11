# DATA13 — current DATA12 gap inventory

Read-only finite screen pinned to DATA12 candidate SHA-256 `6c444950cc89d955231a3fd8dc34cd6f34921734ab3e124ccc81aefd74d7bca9`. DATA10 remains unchanged and describes DATA09 only.

379 of 504 rows have at least one listed open item; 125 have none under this finite screen. None is economically cleared: BUY/ADD remains blocked for all 504. Counts overlap. The three hardcoded prior-amendment items for MCD/CEG/WELL are removed only for the exact candidate containing the verified DATA11/DATA12 corrections. Annual revenue gaps decrease from 54 to 53.

Comparison with the pinned RC1 ledger now finds five numerically equivalent formatting differences and one substantive difference: CEG sbc_to_revenue remains blank because current annual_sbc is missing. The historical ratio 0.015078525829318921 is not copied into the current dataset without verification of its numerator. This is a remaining SBC source gap, not an uncorrected total-revenue denominator. Next targeted source investigation: CEG annual SBC, followed by the remaining material source and economic gaps.

Other open items include 212 leverage-indeterminate rows, 88 missing annual capex observations, 133 missing annual diluted-share observations, 101 missing annual SBC observations, and ten economic cases. Descriptive PRESENT/100% core coverage is not completeness or clearance.

Run `python src/br04_data13_inventory.py` after reconstructing DATA12. It writes the summary, historical comparison and the generated per-row qualification.json. The generated row file is not committed; the source, deterministic summary and comparison are committed. No scoring, candidate mutation, promotion, independent release approval or S6 action occurs.
