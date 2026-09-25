#!/usr/bin/env python3
"""Investment OS V4.2 R8/R9 regression runner.

Reads repository state only. Writes docs receipts/reports.
Does not calculate any real-company BQS/IOS ranking.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data" / "current"
DOCS = ROOT / "docs"

EXPECTED_ENGINE_MD5 = "68f626974592915d6c2a8e6583d6c77b"
EXPECTED_CANONICAL_SHA256 = "d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45"
EXPECTED_ROWS = 504
EXPECTED_COLUMNS = 285
EXPECTED_PARTS = 50

ENGINE = ROOT / "src" / "investment_os" / "v4_1_frozen" / "v4_scoring.py"
V41_TEST = ROOT / "tests" / "v4_1_frozen" / "test_v4.py"
R8_TEST = ROOT / "tests" / "test_sector_variants_v42.py"
CSV = CURRENT / "sp500_fundamentals.csv"
INDEX = CURRENT / "fundamentals_chunks.json"
MANIFEST = CURRENT / "manifest.json"
BLIND_RECEIPT = ROOT / "data" / "blind_v4_1" / "36045268572" / "quantitative" / "FREEZE_RECEIPT.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def csv_records_raw(data: bytes) -> list[bytes]:
    records = []
    start = 0
    i = 0
    in_quotes = False
    while i < len(data):
        b = data[i]
        if b == 0x22:
            if in_quotes and i + 1 < len(data) and data[i + 1] == 0x22:
                i += 2
                continue
            in_quotes = not in_quotes
            i += 1
            continue
        if b == 0x0A and not in_quotes:
            records.append(data[start:i+1])
            start = i + 1
        i += 1
    if in_quotes:
        raise ValueError("Unclosed quoted field")
    if start < len(data):
        records.append(data[start:])
    return records


def run_python(path: Path, pythonpath: Path | None = None) -> dict:
    env = None
    if pythonpath is not None:
        import os
        env = os.environ.copy()
        env["PYTHONPATH"] = str(pythonpath)
    p = subprocess.run([sys.executable, str(path)], cwd=str(ROOT),
                       text=True, capture_output=True, env=env)
    return {
        "exit_code": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "pass_lines": sum(1 for x in p.stdout.splitlines() if x.startswith("[PASS]")),
        "fail_lines": sum(1 for x in p.stdout.splitlines() if x.startswith("[FAIL]")),
    }


def main() -> int:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    # R0/R1 invariants rechecked.
    checks["frozen_engine_exists"] = ENGINE.exists()
    checks["frozen_engine_md5"] = ENGINE.exists() and md5_file(ENGINE) == EXPECTED_ENGINE_MD5

    v41 = run_python(V41_TEST, ENGINE.parent)
    details["v41_regression"] = {
        "exit_code": v41["exit_code"],
        "pass_lines": v41["pass_lines"],
        "fail_lines": v41["fail_lines"],
    }
    checks["v41_regression_pass"] = v41["exit_code"] == 0 and "TUTTI I TEST PASSATI" in v41["stdout"]

    # R8.
    r8 = run_python(R8_TEST)
    details["r8"] = {
        "exit_code": r8["exit_code"],
        "pass_lines": r8["pass_lines"],
        "fail_lines": r8["fail_lines"],
    }
    checks["r8_sector_variant_pass"] = r8["exit_code"] == 0 and "R8 SECTOR-VARIANT REGRESSION PASSED" in r8["stdout"]

    # R9 actual canonical/transport.
    required = [CSV, INDEX, MANIFEST]
    checks["r9_required_files_exist"] = all(p.exists() for p in required)
    if not checks["r9_required_files_exist"]:
        raise SystemExit("R9 required canonical files missing")

    source_raw = CSV.read_bytes()
    source_sha = sha256_bytes(source_raw)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = csv_records_raw(source_raw)

    checks["r9_canonical_sha"] = source_sha == EXPECTED_CANONICAL_SHA256
    checks["r9_index_source_sha"] = index.get("source_sha256") == EXPECTED_CANONICAL_SHA256
    checks["r9_total_rows_index"] = int(index.get("total_rows", -1)) == EXPECTED_ROWS
    checks["r9_total_columns_index"] = int(index.get("total_columns", -1)) == EXPECTED_COLUMNS
    checks["r9_total_parts_index"] = int(index.get("total_parts", -1)) == EXPECTED_PARTS
    checks["r9_raw_record_count"] = len(records) - 1 == EXPECTED_ROWS

    # Parse semantic CSV shape without ranking.
    with CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    checks["r9_csv_rows"] = len(rows) == EXPECTED_ROWS
    checks["r9_csv_columns"] = len(fieldnames) == EXPECTED_COLUMNS
    if "ticker" in fieldnames:
        tickers = [str(r.get("ticker", "")).strip() for r in rows]
        checks["r9_no_blank_ticker"] = all(tickers)
        checks["r9_no_duplicate_ticker"] = len(set(tickers)) == len(tickers)
    else:
        checks["r9_no_blank_ticker"] = False
        checks["r9_no_duplicate_ticker"] = False

    header = records[0]
    hard_max = int(index.get("hard_max_bytes", 0))
    expected_start = 1
    row_sum = 0
    part_hash_failures = 0
    header_failures = 0
    size_failures = 0
    url_failures = 0
    range_failures = 0
    out = bytearray()
    parts = index.get("parts", [])

    for i, p in enumerate(parts):
        path = CURRENT / p["filename"]
        if not path.exists():
            part_hash_failures += 1
            continue
        data = path.read_bytes()
        if sha256_bytes(data) != p.get("sha256"):
            part_hash_failures += 1
        if len(data) > hard_max:
            size_failures += 1
        if not data.startswith(header):
            header_failures += 1

        start = int(p.get("row_start_1_based", 0))
        end = int(p.get("row_end_1_based", 0))
        n = int(p.get("rows", 0))
        if start != expected_start or end != start + n - 1:
            range_failures += 1
        expected_start = end + 1
        row_sum += n

        expected_suffix = f"/data/current/{p['filename']}"
        if not str(p.get("url", "")).endswith(expected_suffix):
            url_failures += 1

        if i == 0:
            out.extend(data)
        else:
            out.extend(data[len(header):])

    reassembled = bytes(out)
    checks["r9_part_count_actual"] = len(parts) == EXPECTED_PARTS
    checks["r9_part_hash_failures_zero"] = part_hash_failures == 0
    checks["r9_header_failures_zero"] = header_failures == 0
    checks["r9_size_failures_zero"] = size_failures == 0
    checks["r9_url_failures_zero"] = url_failures == 0
    checks["r9_range_failures_zero"] = range_failures == 0
    checks["r9_row_sum"] = row_sum == EXPECTED_ROWS
    checks["r9_reassembled_byte_identical"] = reassembled == source_raw
    checks["r9_reassembled_sha"] = sha256_bytes(reassembled) == EXPECTED_CANONICAL_SHA256

    tv = index.get("transport_validation", {})
    checks["r9_index_transport_rows"] = tv.get("rows_match_source") is True
    checks["r9_index_transport_ranges"] = tv.get("ranges_contiguous") is True
    checks["r9_index_transport_size"] = tv.get("all_parts_under_hard_max") is True
    checks["r9_index_transport_byte_identical"] = tv.get("reassembled_byte_identical") is True
    checks["r9_index_transport_sha"] = tv.get("reassembled_sha256") == EXPECTED_CANONICAL_SHA256

    br04 = manifest.get("br04_debt_interest", {})
    checks["r9_manifest_schema_1_4"] = str(manifest.get("schema_version")) == "1.4"
    checks["r9_manifest_s7_verified"] = br04.get("phase") == "S7_VERIFIED"
    checks["r9_manifest_candidate_sha"] = br04.get("candidate_sha256") == EXPECTED_CANONICAL_SHA256
    checks["r9_manifest_t20"] = br04.get("s7_t20_passed") is True
    checks["r9_manifest_post_promotion"] = br04.get("s7_post_promotion_verified") is True
    checks["r9_manifest_urls_current"] = br04.get("transport_urls_scope") == "data/current"

    # Existing blind receipt must still attest direct market cap and frozen canonical.
    if BLIND_RECEIPT.exists():
        b = json.loads(BLIND_RECEIPT.read_text(encoding="utf-8"))
        checks["r9_blind_receipt_canonical_sha"] = b.get("canonical_sha256") == EXPECTED_CANONICAL_SHA256
        checks["r9_market_cap_not_reconstructed"] = (
            b.get("market_snapshot", {}).get("market_cap_reconstructed_from_bridge_shares") is False
            and b.get("rules", {}).get("market_cap_reconstructed_from_bridge_shares") is False
        )
    else:
        checks["r9_blind_receipt_canonical_sha"] = False
        checks["r9_market_cap_not_reconstructed"] = False

    details["r9"] = {
        "canonical_sha256": source_sha,
        "rows": len(rows),
        "columns": len(fieldnames),
        "parts": len(parts),
        "part_hash_failures": part_hash_failures,
        "header_failures": header_failures,
        "size_failures": size_failures,
        "url_failures": url_failures,
        "range_failures": range_failures,
        "reassembled_sha256": sha256_bytes(reassembled),
    }

    failed = sorted(k for k, v in checks.items() if v is not True)
    overall = not failed

    receipt = {
        "schema": "investment_os_v4_2_r8_r9_receipt_v1.0",
        "stage": "R8_R9_REGRESSION",
        "status": "PASS" if overall else "FAIL",
        "system_live": False,
        "real_data_v42_ranking_executed": False,
        "v4_1_modified": False,
        "expected_engine_md5": EXPECTED_ENGINE_MD5,
        "expected_canonical_sha256": EXPECTED_CANONICAL_SHA256,
        "checks": checks,
        "failed_checks": failed,
        "details": details,
        "next_gate": "V4_2_ENGINE_INTEGRATION_PRE_FREEZE" if overall else "BLOCK",
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "V4_2_R8_R9_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    report = f"""# V4.2 R8/R9 — SECTOR VARIANT & TRANSPORT REGRESSION

- Status: **{'PASS' if overall else 'FAIL'}**
- System: **NOT LIVE**
- V4.2 real-data ranking executed: **NO**
- V4.1 modified: **NO**
- Frozen V4.1 engine MD5: `{md5_file(ENGINE) if ENGINE.exists() else 'MISSING'}`
- Canonical SHA-256: `{source_sha}`
- Rows / columns: **{len(rows)} / {len(fieldnames)}**
- Chunks: **{len(parts)}**
- Reassembled SHA-256: `{sha256_bytes(reassembled)}`

## R8

- Frozen V4.1 regression: **{'PASS' if checks['v41_regression_pass'] else 'FAIL'}**
- Sector-variant regression: **{'PASS' if checks['r8_sector_variant_pass'] else 'FAIL'}**
- R8 PASS lines: **{r8['pass_lines']}**
- R8 FAIL lines: **{r8['fail_lines']}**

## R9

Validated against actual `data/current` without calculating rankings:

- canonical SHA;
- 504 rows / 285 columns;
- 50 chunk declarations;
- every chunk SHA;
- hard byte cap;
- common header;
- contiguous row ranges;
- `data/current` URLs;
- byte-identical reassembly;
- reassembled SHA;
- manifest S7_VERIFIED / T20 status;
- frozen blind receipt direct-market-cap invariant;
- no blank/duplicate ticker.

## Failed checks

{chr(10).join('- ' + x for x in failed) if failed else '- none'}

## Conclusion

**{'R8/R9 PASS. Engine integration may proceed, but no real ranking is authorized until the integrated V4.2 engine/adapters are frozen.' if overall else 'BLOCK. Reconcile failed checks before engine integration.'}**
"""
    (DOCS / "V4_2_R8_R9_REGRESSION_REPORT.md").write_text(report, encoding="utf-8")

    (DOCS / "V4_2_R8_OUTPUT.txt").write_text(
        r8["stdout"] + ("\nSTDERR:\n" + r8["stderr"] if r8["stderr"] else ""),
        encoding="utf-8",
    )
    (DOCS / "V4_1_REGRESSION_OUTPUT_R8_R9.txt").write_text(
        v41["stdout"] + ("\nSTDERR:\n" + v41["stderr"] if v41["stderr"] else ""),
        encoding="utf-8",
    )

    print(json.dumps(receipt, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
