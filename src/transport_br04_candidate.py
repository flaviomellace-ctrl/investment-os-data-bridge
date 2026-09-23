#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-04 S3 transport / T20.

Purpose
-------
Run the production splitter against the exact BR-04 S1 candidate, verify
transport integrity, and write aggregate evidence only.

This phase MUST NOT:
- modify data/current/
- modify the candidate CSV
- run BQS/IOS/ranking/Blind Test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import split_for_claude as splitter

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data" / "current" / "sp500_fundamentals.csv"

SCHEMA = "br04_transport_v1.0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"File richiesto non trovato: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--s1-run-id",
        required=True,
        help="Run ID S1 che identifica il candidato BR-04 da verificare",
    )
    args = parser.parse_args()

    s1_run_id = str(args.s1_run_id).strip()
    if not s1_run_id.isdigit():
        raise SystemExit("--s1-run-id deve essere numerico")

    staging = ROOT / "data" / "staging" / "br04" / s1_run_id
    candidate_dir = staging / "candidate"
    evidence_dir = staging / "evidence"

    candidate = candidate_dir / "sp500_fundamentals.csv"
    regression_path = evidence_dir / "br04_regression.json"

    if not candidate.exists():
        raise SystemExit(f"Candidato non trovato: {candidate}")

    regression = load_json(regression_path)

    if regression.get("phase") != "S2":
        raise SystemExit("br04_regression.json non è evidenza S2")

    if regression.get("overall_passed") is not True:
        raise SystemExit("S2 non risulta PASS: S3 è bloccata")

    expected_candidate_sha = str(
        regression.get("candidate_sha256", "")
    ).strip()
    base_sha = str(
        regression.get("base_canonical_sha256", "")
    ).strip()

    if not expected_candidate_sha or not base_sha:
        raise SystemExit(
            "Catena di custodia incompleta in br04_regression.json"
        )

    if not CURRENT.exists():
        raise SystemExit(f"Canonico non trovato: {CURRENT}")

    current_before_sha = sha256_file(CURRENT)
    if current_before_sha != base_sha:
        raise SystemExit(
            "S3_BLOCK_BASE_CHANGED: data/current non coincide più con la "
            "base approvata da S2. Rieseguire la catena sulla nuova base."
        )

    before_sha = sha256_file(candidate)
    if before_sha != expected_candidate_sha:
        raise SystemExit(
            "SHA candidato diverso da quello approvato da S2"
        )

    # Run the exact production splitter on the candidate, in staging only.
    index = splitter.split_file(
        source=candidate,
        output_dir=candidate_dir,
        url_base=None,
    )

    after_sha = sha256_file(candidate)
    if after_sha != before_sha:
        raise SystemExit(
            "ERRORE CRITICO: il candidato è cambiato durante S3"
        )

    current_after_sha = sha256_file(CURRENT)
    if current_after_sha != current_before_sha:
        raise SystemExit(
            "ERRORE CRITICO: data/current è cambiato durante S3"
        )

    index_path = candidate_dir / "fundamentals_chunks.json"
    stored_index = load_json(index_path)

    validation = stored_index.get("transport_validation", {})
    parts = stored_index.get("parts", [])

    # Independently verify every written chunk hash.
    part_hash_failures = 0
    for part in parts:
        path = candidate_dir / str(part.get("filename", ""))
        expected = str(part.get("sha256", ""))
        if (
            not path.exists()
            or not expected
            or sha256_file(path) != expected
        ):
            part_hash_failures += 1

    checks = {
        "rows_match_source": validation.get("rows_match_source") is True,
        "ranges_contiguous": validation.get("ranges_contiguous") is True,
        "all_parts_under_hard_max": (
            validation.get("all_parts_under_hard_max") is True
        ),
        "source_sha256_verified": (
            stored_index.get("source_sha256") == expected_candidate_sha
        ),
        "reassembled_byte_identical": (
            validation.get("reassembled_byte_identical") is True
        ),
        "reassembled_sha256_verified": (
            validation.get("reassembled_sha256")
            == expected_candidate_sha
        ),
        "all_part_sha256_verified": part_hash_failures == 0,
        "candidate_unchanged_by_s3": after_sha == before_sha,
        "canonical_unchanged_by_s3": (
            current_after_sha == current_before_sha == base_sha
        ),
        "s2_chain_of_custody_match": (
            regression.get("candidate_sha256") == before_sha
            and regression.get("base_canonical_sha256") == current_before_sha
        ),
    }

    overall_passed = all(checks.values())

    evidence = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "S3",
        "implementation_revision": "br04_s3_transport_r2",
        "s3_run_id": os.getenv("GITHUB_RUN_ID"),
        "s1_run_id": s1_run_id,
        "base_canonical_sha256": base_sha,
        "canonical_sha256_before_s3": current_before_sha,
        "canonical_sha256_after_s3": current_after_sha,
        "candidate_sha256": before_sha,
        "candidate_rows": stored_index.get("total_rows"),
        "candidate_columns": stored_index.get("total_columns"),
        "total_parts": stored_index.get("total_parts"),
        "splitter_schema": stored_index.get("schema"),
        "splitter_byte_preserving": (
            stored_index.get("byte_preserving") is True
        ),
        "target_max_bytes": stored_index.get("target_max_bytes"),
        "hard_max_bytes": stored_index.get("hard_max_bytes"),
        "test": {
            "id": "BR04-T20",
            "status": "PASS" if overall_passed else "FAIL",
            "checks": checks,
            "part_hash_failures": part_hash_failures,
        },
        "overall_passed": overall_passed,
        "invariants": [
            "Candidate CSV was not modified by S3.",
            "data/current was not modified by S3.",
            "Chunks were generated from the exact S1 candidate.",
            "Reassembly is byte-identical to the candidate.",
            "No ranking, BQS, IOS, recommendation or Blind Test was executed.",
        ],
    }

    evidence_dir.mkdir(parents=True, exist_ok=True)
    out = evidence_dir / "br04_transport.json"
    out.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md = [
        "# BR-04 S3 Transport — T20",
        "",
        f"- S1 run ID: **{s1_run_id}**",
        f"- Candidate SHA-256: `{before_sha}`",
        f"- Base canonical SHA-256: `{base_sha}`",
        f"- Parts: **{stored_index.get('total_parts')}**",
        f"- Rows: **{stored_index.get('total_rows')}**",
        f"- Columns: **{stored_index.get('total_columns')}**",
        f"- Splitter byte-preserving: **{stored_index.get('byte_preserving') is True}**",
        "",
        "## BR04-T20",
        "",
    ]

    for name, passed in checks.items():
        md.append(f"- {name}: **{'PASS' if passed else 'FAIL'}**")

    md.extend(
        [
            "",
            f"## Overall: **{'PASS' if overall_passed else 'FAIL'}**",
            "",
            "Nessun file in `data/current/` è stato modificato.",
            "",
        ]
    )

    (evidence_dir / "br04_transport.md").write_text(
        "\n".join(md),
        encoding="utf-8",
    )

    print(
        f"BR04 S3 / T20: {'PASS' if overall_passed else 'FAIL'}"
    )
    print(f"candidate_sha256={before_sha}")
    print(f"parts={stored_index.get('total_parts')}")
    print(
        "reassembled_byte_identical="
        f"{validation.get('reassembled_byte_identical')}"
    )

    if not overall_passed:
        failed = [k for k, v in checks.items() if not v]
        print("Failed checks: " + ", ".join(failed))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
