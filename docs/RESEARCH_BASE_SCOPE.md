# Frozen replay versus current base

DATA14 regression tests now read a hash-pinned archived fixture. Production data/current is never overwritten by fixture recovery. The full frozen research pipeline checks out the explicit PR head, reconstructs the candidate and binds all 41 economic flags to ten cases. Its passing result is research compatibility, not release approval.

A separate current-base-compatibility job checks the merged PR base and fails when its actual current-data SHA differs from the research base. This remains an explicit rebase blocker; changing the expected hash alone is not reconciliation.

Economic-gate outputs preserve all 504 BUY/ADD blocks. R11 and R12 remain NOT EXECUTED. No clearance follows from absent flags or computable IOS.
