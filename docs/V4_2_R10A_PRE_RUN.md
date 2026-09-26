# V4.2 R10A — PRE-RUN

R10 produced `MAJOR_IOS_NUMERIC_POOL_LOSS`: 309 numeric IOS in V4.1 versus 159 in V4.2, with 150 previously numeric rows blocked.

R10A audits only those 150 rows. It distinguishes deterministic derivation defects, direct-source extraction gaps, missing historical dependencies, economically non-computable series, and multi-cause cases.

R10A MUST NOT change the V4.2 engine, G2, BQS/IOS weights, Lane-I thresholds, the 7+3 merge, `data/current`, market data, or validation targets. It fetches no external data and never maps MISSING to zero.

After R10A, any data repair must be built in a separate V4.2 candidate data layer. The V4.1 canonical remains immutable.

**System remains NOT LIVE.**
