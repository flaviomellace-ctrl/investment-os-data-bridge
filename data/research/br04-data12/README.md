# DATA12 — scoped consolidated revenue policy for CEG and WELL

Research-only amendment of DATA11 (`c856d8af683e1b4ca8d21ba3c8258b7a19714301964209f9176893728a33b486`). Output SHA-256: `6c444950cc89d955231a3fd8dc34cd6f34921734ab3e124ccc81aefd74d7bca9`.

The bridge prefers RevenueFromContractWithCustomerExcludingAssessedTax before Revenues. These tags are not interchangeable for these issuers. WELL's current 2023–2025 fields contain resident fees and services, whereas its 2022 field contains total revenues. CEG lacks 2025 revenue but already uses consolidated total revenues for 2022–2024. The explicit policy here uses reported consolidated total revenues for both companies over all four years. This policy is scoped to these two research rows; the bridge-wide precedence is unchanged.

| Issuer | 2025 | 2024 | 2023 | 2022 |
|---|---:|---:|---:|---:|
| CEG (USD) | 25,533,000,000 | 23,568,000,000 | 24,918,000,000 | 24,440,000,000 |
| WELL (USD) | 10,838,034,000 | 7,991,118,000 | 6,637,995,000 | 5,860,615,000 |

WELL's total includes resident fees, rental income, interest income and other income. CEG's total includes contract and other revenues. These are reported total-revenue denominators, not organic-growth, comparable-store, or recurring-revenue measures. Growth also reflects business/perimeter changes.

Evidence: the unchanged pinned DATA10 proof bundle and original acquisition receipt. Archive verification rehashes every receipt-listed source, checks the eight Company Facts observations against all annual observations available by each 2025 filing date (2026-02-24 CEG, 2026-02-12 WELL), and matches six 2023–2025 observations to the current filing's extracted instance and scoped inline table. The two 2022 observations are Company Facts-backed, not newly verified against inline tables. No fresh SEC acquisition occurred.

`amendment.json` supplies field-level accession, period, concept and source hashes. Revenue uses the latest comparative available by the annual filing cutoff; historical row-level accessions remain unchanged because those describe other historical inputs. Consumers must retain this sidecar for amended revenue provenance. Existing operating income, FCF, net income and SBC numerators are retained from the exact DATA11 input, not re-audited by this revenue amendment.

Exactly 25 cells change: 14 CEG and 11 WELL. Revenue-dependent ratios and four-year margin dispersion are recomputed. Numerically equivalent strings retain existing precision. CEG's revenue date, descriptive coverage, missing-revenue flag and data status are updated coherently. PRESENT/100% describes the existing bridge's finite core-field screen, not economic completeness. WELL's unavailable operating-income and FCF margins remain blank. All 502 other rows and every BR04 field are preserved. BR04 FSDS_FACE_ONLY continues to describe the unchanged BR04 component source scope; amended revenue provenance is in the sidecar.

Reproduce after DATA11 reconstruction:

```
python src/br04_data12_revenue.py --engine
```

Optionally revalidate the pinned raw archive using `--archive PATH` (requires lxml and exactly the receipt-listed archive inventory). The candidate CSV is generated, not committed. Tests verify exact reproducibility, scope, revenue series, derived metrics, preservation of missing inputs, tamper rejection and rejection of double application.

The frozen-engine compatibility check reports aggregate results only. DATA09 S2/S3/S4 approvals do not transfer to this amended candidate. Independent economic validation, R11/R12 and promotion remain outstanding. No LIVE, BUY/ADD, or S6 authorization. The prior DATA10 inventory remains tied to DATA09 and must not be represented as the DATA12 gap count.
