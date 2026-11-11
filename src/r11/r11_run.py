#!/usr/bin/env python3
"""R11 executor runner. Runs the frozen integrated pipeline on a sealed control file.

It does not score anything and holds no expected outcome. Each case is executed twice
to prove determinism. Output: raw results, environment and SHA-256 hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import v42_integrated_pipeline as ip  # noqa: E402

CASES_SCHEMA = "investment_os_r11_control_cases_v1"
OUTPUT_SCHEMA = "investment_os_r11_executor_output_v1"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cases", required=True)
    p.add_argument("--expect-cases-sha256", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    raw = Path(a.cases).read_bytes()
    cases_sha = hashlib.sha256(raw).hexdigest()
    if cases_sha != a.expect_cases_sha256:
        raise SystemExit("control file hash mismatch: do not run")
    doc = json.loads(raw)
    if doc.get("schema") != CASES_SCHEMA:
        raise SystemExit("control file schema mismatch")
    components = ip.load_components()
    results, exceptions = [], []
    for case in doc["cases"]:
        entry = dict(case_id=case["case_id"])
        try:
            runs = []
            for _ in range(2):
                out = ip.run(json.loads(json.dumps(case["rows"])),
                             dict(schema=ip.EVIDENCE_SCHEMA, entities=json.loads(json.dumps(case.get("evidence") or {}))),
                             components=components, economic_registry=case.get("economic_registry") or None)
                runs.append(ip.canonical_json(out))
            entry["deterministic"] = runs[0] == runs[1]
            entry["result_sha256"] = hashlib.sha256(runs[0]).hexdigest()
            entry["result"] = json.loads(runs[0])
        except Exception as exc:  # recorded, never hidden
            entry["exception"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
            exceptions.append(case["case_id"])
        results.append(entry)
    payload = dict(schema=OUTPUT_SCHEMA, control_set_id=doc.get("control_set_id"), cases_sha256=cases_sha,
                   pipeline_version=ip.PIPELINE_VERSION, component_sha256={k: v[1] for k, v in sorted(ip.FROZEN_COMPONENTS.items())},
                   orchestrator_sha256=hashlib.sha256(Path(ip.__file__).read_bytes()).hexdigest(),
                   runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   environment=dict(python=sys.version, implementation=platform.python_implementation(), platform=platform.platform()),
                   case_count=len(results), exceptions=exceptions,
                   all_deterministic=all(r.get("deterministic") is True for r in results), results=results)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, sort_keys=True, indent=1, allow_nan=False) + "\n").encode()
    (out / "R11_EXECUTOR_OUTPUT.json").write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    (out / "R11_EXECUTOR_OUTPUT.sha256").write_text(digest + "  R11_EXECUTOR_OUTPUT.json\n")
    print(json.dumps(dict(cases=len(results), exceptions=exceptions, all_deterministic=payload["all_deterministic"],
                          output_sha256=digest, verdict="NOT_SCORED_BY_EXECUTOR")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
