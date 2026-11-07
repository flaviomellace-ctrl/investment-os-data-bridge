#!/usr/bin/env python3
"""
Investment OS Data Bridge — BR-04 S4 / BR04-T18 engine preflight.

Runs the frozen V4.1 scoring engine against the exact S3 candidate chunks in
staging, emits aggregate evidence only, and never reads from or writes to
`data/current/`.

This phase MUST NOT:
- emit tickers, company names, rankings, Top lists, recommendations, or
  individual BQS/IOS values;
- execute the Blind Test;
- modify the candidate or promote it to data/current/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "data/research/br04-data09/runtime/v4_scoring.py"
EXPECTED_ENGINE_MD5 = "68f626974592915d6c2a8e6583d6c77b"
SCHEMA = "br04_data09_research_engine_v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"File richiesto non trovato: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def csv_records_raw(data: bytes) -> list[bytes]:
    """Split CSV into raw records while preserving every byte."""
    if not data:
        return []
    records: list[bytes] = []
    start = 0
    i = 0
    in_quotes = False
    while i < len(data):
        b = data[i]
        if b == 0x22:  # quote
            if in_quotes and i + 1 < len(data) and data[i + 1] == 0x22:
                i += 2
                continue
            in_quotes = not in_quotes
            i += 1
            continue
        if b == 0x0A and not in_quotes:
            records.append(data[start : i + 1])
            start = i + 1
        i += 1
    if in_quotes:
        raise ValueError("CSV non valido: campo quotato non chiuso")
    if start < len(data):
        records.append(data[start:])
    return records


def load_frozen_engine():
    if not ENGINE_PATH.exists():
        raise SystemExit(f"Motore V4.1 non trovato: {ENGINE_PATH}")
    actual_md5 = md5_file(ENGINE_PATH)
    if actual_md5 != EXPECTED_ENGINE_MD5:
        raise SystemExit(
            "S4_BLOCK_ENGINE_MD5: il motore V4.1 non coincide con il motore congelato "
            f"(atteso {EXPECTED_ENGINE_MD5}, trovato {actual_md5})"
        )
    spec = importlib.util.spec_from_file_location("v4_scoring_frozen", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("Impossibile caricare il motore V4.1")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod, actual_md5


def num(v):
    if v in (None, "", "nan", "None", "MISSING", "NA"):
        return None
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def module_of(sic):
    if sic is None:
        return "UNKNOWN"
    s = int(sic)
    if s in (6021, 6022, 6020, 6035, 6036, 6199, 6141, 6159, 6162, 6172):
        return "BANK"
    if s in (6311, 6321, 6324, 6331, 6399, 6411, 6300, 6351):
        return "INSURANCE"
    if s in (6798, 6510, 6500, 6512, 6792, 6552, 6531):
        return "REIT"
    if 4900 <= s <= 4991:
        return "UTILITY"
    if s in (6211, 6282, 6200, 6221):
        return "ASSETMGR_EXCH"
    if s in (1311, 1389, 2911, 1000, 1040, 1400, 1220, 2870, 3533):
        return "RESOURCES"
    if s in (3674, 3559, 3827, 3825, 3576, 3572, 3571, 3577, 3661, 3663, 3670, 3672):
        return "SEMICONDUCTOR"
    if s in (7372, 7370, 7371, 7373, 7374, 7389, 7379):
        return "SOFTWARE"
    if 3400 <= s <= 3569 or 3580 <= s <= 3600 or s in (3711, 3714, 3721, 3728, 3812, 8711, 1731):
        return "INDUSTRIAL"
    return "GENERAL"


def derive(row: dict[str, str], engine) -> dict[str, Any]:
    """Adapter recovered from the original S4 preflight; no scoring formulas are changed."""
    g = lambda k: num(row.get(k))
    rev = g("annual_revenue")
    ni = g("annual_net_income")
    ocf = g("annual_operating_cash_flow")
    capex = g("annual_capex")
    eq = g("annual_equity")
    assets = g("annual_assets")

    c: dict[str, Any] = {}
    c["module"] = module_of(g("sic"))
    c["data_coverage_pct"] = g("core_metric_coverage_pct")
    c["op_margin"] = g("operating_margin")
    c["fcf_margin"] = g("fcf_margin")
    c["net_margin"] = g("net_margin")
    c["roe"] = g("roe_simple")

    def br04(key: str):
        v = (row.get(key) or "").strip()
        if v == "":
            return None
        if v == "NOT_APPLICABLE":
            return engine.NA
        if v == "CONFLICTING":
            return engine.CONFLICTING
        return g(key)

    c["roic"] = br04("roic")
    c["cash_conversion"] = (ocf / ni) if (ocf is not None and ni) else None
    c["accrual_quality"] = c["cash_conversion"]
    c["equity_to_assets"] = (eq / assets) if (eq is not None and assets) else None
    c["net_debt_to_ocf"] = br04("net_debt_to_ocf")
    c["reinvestment_rate"] = (capex / rev) if (capex is not None and rev) else None
    c["share_change"] = g("diluted_shares_yoy")
    c["ni_yoy"] = g("net_income_yoy")
    c["book_value"] = eq
    c["ocf"] = ocf
    c["capex"] = capex

    c["revenue_cagr3"] = g("revenue_cagr3")
    c["opinc_cagr3"] = g("opinc_cagr3")
    c["fcf_cagr3"] = g("fcf_cagr3")
    c["fcf_per_share_cagr3"] = g("fcf_per_share_cagr3")
    c["margin_stability"] = g("operating_margin_std_4y")

    c["sbc"] = g("annual_sbc")
    c["sbc_to_revenue"] = g("sbc_to_revenue")

    c["market_cap"] = g("market_cap")
    c["price"] = g("market_price")
    c["market_data_source"] = row.get("market_data_source") or None
    c["market_data_as_of"] = row.get("market_data_as_of") or None
    c["market_data_status"] = row.get("market_data_status") or None

    ba = row.get("buyback_accretion", "")
    c["buyback_accretion"] = engine.NA if ba == "NOT_APPLICABLE" else g("buyback_accretion")
    c["payout_ratio"] = g("payout_ratio")

    c["interest_coverage"] = br04("interest_coverage")
    for key in (
        "retention",
        "unit_cost_decline",
        "two_sided_growth",
        "frequency_growth",
        "combined_ratio",
        "ffo_margin",
        "occupancy",
        "ebitda_on_volume",
        "fcf_on_volume",
        "take_rate",
        "affo",
    ):
        c[key] = None
    return c


def raw_field_state(value: str | None) -> str:
    v = (value or "").strip()
    if not v or v in ("MISSING", "NA", "None", "nan"):
        return "MISSING"
    if v == "NOT_APPLICABLE":
        return "NOT_APPLICABLE"
    if v == "CONFLICTING":
        return "CONFLICTING"
    try:
        float(v)
        return "NUMERIC"
    except ValueError:
        return "OTHER"


def ordered_counter(counter: Counter) -> dict[str, int]:
    return {k: counter[k] for k in sorted(counter)}


def main() -> int:
    from br04_data09_runtime import approved_regression
    s1_run_id = "40122845921"
    candidate_dir = ROOT / "data/research/br04-data09"
    evidence_dir = candidate_dir
    candidate_path = candidate_dir / "RESEARCH_NOT_PROMOTED.csv"
    index_path = candidate_dir / "fundamentals_chunks.json"
    transport_path = candidate_dir / "research_transport.json"
    regression = approved_regression(ROOT)

    engine, engine_md5 = load_frozen_engine()

    transport = load_json(transport_path)
    index = load_json(index_path)

    if regression.get("phase") != "S2_RESEARCH" or regression.get("overall_passed") is not True:
        raise SystemExit("S4_BLOCK_S2: S2 non risulta PASS")
    if transport.get("phase") != "S3_RESEARCH" or transport.get("overall_passed") is not True:
        raise SystemExit("S4_BLOCK_S3: S3/T20 non risulta PASS")
    if index.get("byte_preserving") is not True:
        raise SystemExit("S4_BLOCK_TRANSPORT: splitter non byte-preserving")

    expected_candidate_sha = str(regression.get("candidate_sha256", "")).strip()
    base_sha = str(regression.get("base_canonical_sha256", "")).strip()
    if not expected_candidate_sha or not base_sha:
        raise SystemExit("S4_BLOCK_CUSTODY: hash di catena mancanti")

    if transport.get("candidate_sha256") != expected_candidate_sha:
        raise SystemExit("S4_BLOCK_CUSTODY: S2/S3 candidate_sha256 differiscono")
    if transport.get("base_canonical_sha256") != base_sha:
        raise SystemExit("S4_BLOCK_CUSTODY: S2/S3 base_canonical_sha256 differiscono")
    if index.get("source_sha256") != expected_candidate_sha:
        raise SystemExit("S4_BLOCK_CUSTODY: chunk manifest non punta al candidato S2")

    parts_meta = sorted(index.get("parts") or [], key=lambda x: int(x.get("part", 0)))
    declared_parts = int(index.get("total_parts", 0))
    if declared_parts < 1 or len(parts_meta) != declared_parts:
        raise SystemExit("S4_BLOCK_TRANSPORT: numero chunk non coerente")

    reassembled = bytearray()
    header: bytes | None = None
    rows_from_parts = 0
    part_hash_failures = 0
    ranges_contiguous = True
    all_parts_under_hard_max = True
    expected_start = 1
    hard_max = int(index.get("hard_max_bytes", 0) or 0)

    for idx, meta in enumerate(parts_meta):
        filename = str(meta.get("filename", ""))
        path = candidate_dir / filename
        if not path.exists():
            raise SystemExit(f"S4_BLOCK_TRANSPORT: chunk mancante {filename}")
        data = path.read_bytes()
        if sha256_bytes(data) != str(meta.get("sha256", "")):
            part_hash_failures += 1
        if int(meta.get("bytes", -1)) != len(data):
            part_hash_failures += 1
        if hard_max and len(data) > hard_max:
            all_parts_under_hard_max = False

        records = csv_records_raw(data)
        if not records:
            raise SystemExit(f"S4_BLOCK_TRANSPORT: chunk vuoto {filename}")
        if header is None:
            header = records[0]
        elif records[0] != header:
            raise SystemExit(f"S4_BLOCK_TRANSPORT: header incoerente {filename}")

        actual_rows = len(records) - 1
        if actual_rows != int(meta.get("rows", -1)):
            raise SystemExit(f"S4_BLOCK_TRANSPORT: row count incoerente {filename}")
        rows_from_parts += actual_rows

        start = int(meta.get("row_start_1_based", 0))
        end = int(meta.get("row_end_1_based", -1))
        if start != expected_start or end != start + actual_rows - 1:
            ranges_contiguous = False
        expected_start = end + 1

        if idx == 0:
            reassembled.extend(data)
        else:
            reassembled.extend(b"".join(records[1:]))

    reassembled_bytes = bytes(reassembled)
    reassembled_sha = sha256_bytes(reassembled_bytes)
    candidate_sha_verified = reassembled_sha == expected_candidate_sha

    if candidate_path.exists():
        candidate_sha_file = sha256_file(candidate_path)
        candidate_byte_identical = candidate_path.read_bytes() == reassembled_bytes
    else:
        candidate_sha_file = ""
        candidate_byte_identical = False

    rows_declared = int(index.get("total_rows", 0))
    columns_declared = int(index.get("total_columns", 0))
    rows_match_source = rows_from_parts == rows_declared
    ranges_contiguous = ranges_contiguous and (expected_start - 1 == rows_declared)
    reassembled_byte_identical = candidate_byte_identical and candidate_sha_verified
    source_sha_verified = candidate_sha_file == expected_candidate_sha

    if header is None:
        raise SystemExit("S4_BLOCK_TRANSPORT: header non disponibile")
    header_text = header.decode("utf-8-sig").rstrip("\r\n")
    columns_read = len(next(csv.reader([header_text])))

    transport_independent = {
        "part_sha256_failures": part_hash_failures,
        "ranges_contiguous": ranges_contiguous,
        "all_parts_under_hard_max": all_parts_under_hard_max,
        "reassembled_sha256_matches_source": candidate_sha_verified,
    }

    transport_ok = (
        part_hash_failures == 0
        and rows_match_source
        and ranges_contiguous
        and all_parts_under_hard_max
        and reassembled_byte_identical
        and source_sha_verified
        and columns_read == columns_declared
    )
    if not transport_ok:
        raise SystemExit("S4_BLOCK_TRANSPORT: verifica indipendente T20 fallita")

    text = reassembled_bytes.decode("utf-8-sig")
    rows = list(csv.DictReader(text.splitlines()))
    if len(rows) != rows_declared:
        raise SystemExit("S4_BLOCK_ROWS: righe CSV lette diverse dal manifest")

    confidence = Counter()
    bands = Counter()
    provisional_components = Counter()
    ios_by_variant: dict[str, dict[str, int]] = defaultdict(lambda: {"at_gate": 0, "computable": 0})
    ios_blocked = Counter()
    br04_field_states = {
        "net_debt_to_ocf": Counter(),
        "interest_coverage": Counter(),
        "roic": Counter(),
    }
    total_debt_status = Counter()
    interest_status = Counter()
    br04_status = Counter()
    br04_flags = Counter()
    ios_leverage_indeterminate_rows = 0
    exception_counts = Counter()
    gate_count = 0
    ios_computable_total = 0

    for row in rows:
        try:
            c = derive(row, engine)
            score, bqs_cov, detail, _flags = engine.bqs(c)
            conf = engine.bqs_confidence(
                bqs_cov,
                c.get("data_coverage_pct") or 0,
                "PRESENT",
                detail.get("_metric_coverage_pct", 0),
                detail.get("_provisional_components", []),
            )
            confidence[conf] += 1
            for comp in detail.get("_provisional_components", []):
                provisional_components[comp] += 1

            if score is None:
                bands["non_calcolabile"] += 1
            elif score < 60:
                bands["<60"] += 1
            elif score < 70:
                bands["60-69"] += 1
            elif score < 80:
                bands["70-79"] += 1
            elif score < 90:
                bands["80-89"] += 1
            else:
                bands[">=90"] += 1

            data_cov = c.get("data_coverage_pct") or 0
            if score is not None and score >= engine.IOS_GATE["min_bqs"] and data_cov >= engine.IOS_GATE["min_data_coverage"]:
                gate_count += 1
                mod = c.get("module", "GENERAL")
                variant = engine.ios_variant(mod if mod != "UNKNOWN" else "GENERAL")
                ios_by_variant[variant]["at_gate"] += 1
                ios_score, ios_detail = engine.ios(c, score, bqs_cov)
                if ios_score is not None:
                    ios_computable_total += 1
                    ios_by_variant[variant]["computable"] += 1
                else:
                    reason = str(ios_detail.get("gate", "UNKNOWN"))
                    ios_blocked[f"{variant} :: {reason}"] += 1
        except Exception as exc:  # aggregate-only: no ticker/row identifier is recorded
            exception_counts[f"{type(exc).__name__}: {exc}"] += 1

        for key in br04_field_states:
            br04_field_states[key][raw_field_state(row.get(key))] += 1
        total_debt_status[(row.get("total_debt_status") or "MISSING").strip() or "MISSING"] += 1
        interest_status[(row.get("interest_status") or "MISSING").strip() or "MISSING"] += 1
        br04_status[(row.get("br04_status") or "MISSING").strip() or "MISSING"] += 1
        for flag in filter(None, (x.strip() for x in (row.get("br04_flags") or "").split(";"))):
            br04_flags[flag] += 1
        if (row.get("ios_leverage_indeterminate") or "").strip().lower() == "true":
            ios_leverage_indeterminate_rows += 1

    exception_details = [
        {"exception": key, "count": exception_counts[key]}
        for key in sorted(exception_counts)
    ]
    exceptions = sum(exception_counts.values())

    aggregate = {
        "rows_evaluated": len(rows),
        "bqs_confidence_distribution": ordered_counter(confidence),
        "bqs_non_provisional": len(rows) - confidence.get("PROVISIONAL", 0),
        "bqs_provisional": confidence.get("PROVISIONAL", 0),
        "bqs_band_distribution_counts_only": ordered_counter(bands),
        "gate_bqs60_coverage70": gate_count,
        "ios_computable_total": ios_computable_total,
        "ios_computable_by_variant": {
            key: ios_by_variant[key] for key in sorted(ios_by_variant)
        },
        "ios_blocked_reasons_counts": ordered_counter(ios_blocked),
        "provisional_components_counts": ordered_counter(provisional_components),
        "br04_field_states": {
            key: ordered_counter(value) for key, value in br04_field_states.items()
        },
        "br04_total_debt_status": ordered_counter(total_debt_status),
        "br04_interest_status": ordered_counter(interest_status),
        "br04_status": ordered_counter(br04_status),
        "br04_flag_counts": ordered_counter(br04_flags),
        "ios_leverage_indeterminate_rows": ios_leverage_indeterminate_rows,
    }

    overall_passed = (
        engine_md5 == EXPECTED_ENGINE_MD5
        and candidate_sha_verified
        and transport_ok
        and len(rows) == rows_declared
        and columns_read == columns_declared
        and exceptions == 0
    )

    report = {
        "schema": SCHEMA,
        "phase": "S4_RESEARCH",
        "original_fsds_contract_approval": False,
        "buy_add_allowed": False,
        "test_id": "BR04-T18",
        "implementation_revision": "br04_s4_engine_preflight_r1",
        "s4_run_id": os.getenv("GITHUB_RUN_ID"),
        "generated_at_utc": now_iso(),
        "engine_md5": engine_md5,
        "expected_engine_md5": EXPECTED_ENGINE_MD5,
        "engine_md5_verified": engine_md5 == EXPECTED_ENGINE_MD5,
        "candidate_sha256": reassembled_sha,
        "expected_candidate_sha256": expected_candidate_sha,
        "candidate_sha256_verified": candidate_sha_verified,
        "base_canonical_sha256": base_sha,
        "base_scope": transport.get("base_scope", "CURRENT_CANONICAL"),
        "s1_run_id": s1_run_id,
        "source": "data/research/br04-data09 (chunks)",
        "read_from_data_current": False,
        "chunks_declared": declared_parts,
        "chunks_read": len(parts_meta),
        "rows_declared": rows_declared,
        "rows_read": len(rows),
        "columns": columns_read,
        "transport_validation": {
            "rows_from_parts": rows_from_parts,
            "rows_match_source": rows_match_source,
            "ranges_contiguous": ranges_contiguous,
            "all_parts_under_hard_max": all_parts_under_hard_max,
            "reassembled_byte_identical": reassembled_byte_identical,
            "reassembled_sha256": reassembled_sha,
        },
        "transport_independently_verified": transport_independent,
        "exceptions": exceptions,
        "exception_details": exception_details,
        "aggregate_preflight_statistics": aggregate,
        "individual_data_emitted": False,
        "ranking_emitted": False,
        "tickers_emitted": False,
        "blind_test_executed": False,
        "data_current_modified": False,
        "candidate_promoted": False,
        "overall_passed": overall_passed,
    }

    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = evidence_dir / "research_engine.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = [
        "# BR-04 S4 Engine Preflight — BR04-T18",
        "",
        f"- S1 run ID: **{s1_run_id}**",
        f"- S4 run ID: **{os.getenv('GITHUB_RUN_ID') or 'local'}**",
        f"- Candidate SHA-256: `{reassembled_sha}`",
        f"- Base canonical SHA-256: `{base_sha}`",
        f"- Frozen engine MD5: `{engine_md5}`",
        f"- Engine MD5 verified: **{engine_md5 == EXPECTED_ENGINE_MD5}**",
        f"- Chunks read: **{len(parts_meta)}/{declared_parts}**",
        f"- Rows evaluated: **{len(rows)}**",
        f"- Exceptions: **{exceptions}**",
        f"- Overall: **{'PASS' if overall_passed else 'FAIL'}**",
        "",
        "Only aggregate statistics were emitted. No ticker, company name, individual BQS/IOS, ranking, recommendation, or Blind Test was produced.",
        "`data/current/` was neither read nor modified by S4.",
        "",
    ]
    (evidence_dir / "research_engine.md").write_text("\n".join(md), encoding="utf-8")

    print("BR-04 S4 / T18 completed.")
    print(f"s1_run_id={s1_run_id}")
    print(f"engine_md5={engine_md5}")
    print(f"candidate_sha256={reassembled_sha}")
    print(f"rows={len(rows)}")
    print(f"exceptions={exceptions}")
    print(f"overall_passed={str(overall_passed).lower()}")
    print(f"report={json_path.relative_to(ROOT)}")
    print("individual data emitted: NO")
    print("ranking emitted: NO")
    print("blind test executed: NO")
    print("data/current read: NO")
    print("data/current modified: NO")

    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
