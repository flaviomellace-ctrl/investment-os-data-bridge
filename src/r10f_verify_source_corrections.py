"""Verify reviewed, accession-pinned source corrections. Never writes engine inputs.

Requires requirements-r10f.txt. All entity-specific selections live in reviewed data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from lxml import html


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_text(element):
    return re.sub(r"\s+", " ", " ".join(element.itertext())).strip()


def context_record(root, ref):
    matches = [x for x in root.iter() if x.tag.endswith(":context") and x.get("id") == ref]
    if len(matches) != 1:
        raise ValueError("CONTEXT_NOT_UNIQUE")
    c = matches[0]
    fields = {}
    for key in ("startdate", "enddate", "instant", "identifier"):
        values = [normalized_text(x) for x in c.iter() if x.tag.split(":")[-1] == key]
        fields[key] = values
    fields["dimensions"] = sorted([
        {"tag": x.tag, "dimension": x.get("dimension"), "value": normalized_text(x)}
        for x in c.iter() if x.tag.endswith((":explicitmember", ":typedmember"))
    ], key=lambda x: json.dumps(x, sort_keys=True))
    return fields


def fact_value(element):
    if element.get("xsi:nil", "").lower() in ("true", "1"):
        raise ValueError("NIL_IS_NOT_ZERO")
    fmt = element.get("format", "").split(":")[-1]
    if fmt not in ("", "num-dot-decimal", "fixed-zero", "numdash"):
        raise ValueError("UNSUPPORTED_TRANSFORM")
    raw = normalized_text(element).replace(",", "").replace(" ", "")
    if fmt in ("fixed-zero", "numdash"):
        if raw not in ("—", "–", "-", "0"):
            raise ValueError("INVALID_ZERO_TRANSFORM")
        number = Decimal(0)
    else:
        if not re.fullmatch(r"\d+(?:\.\d+)?", raw):
            raise ValueError("INVALID_NUMERIC_FACT")
        number = Decimal(raw)
    if element.get("sign", "") not in ("", "-"):
        raise ValueError("INVALID_SIGN")
    return number * (Decimal(10) ** int(element.get("scale", "0"))) * (-1 if element.get("sign") == "-" else 1)


def verify_fact(root, spec, period):
    matches = [x for x in root.iter() if x.tag.endswith(":nonfraction") and x.get("id") == spec["id"]]
    if len(matches) != 1:
        raise ValueError("FACT_NOT_UNIQUE")
    element = matches[0]
    if dict(element.attrib) != spec["attributes"]:
        raise ValueError("FACT_ATTRIBUTES_CHANGED")
    context = context_record(root, element.get("contextref"))
    if context != spec["context"]:
        raise ValueError("CONTEXT_SCOPE_CHANGED")
    end = context["instant"] or context["enddate"]
    if end != [period]:
        raise ValueError("PERIOD_MISMATCH")
    if context["startdate"]:
        duration = (date.fromisoformat(period) - date.fromisoformat(context["startdate"][0])).days
        if not 330 <= duration <= 380:
            raise ValueError("NONANNUAL_DURATION")
    units = [x for x in root.iter() if x.tag.endswith(":unit") and x.get("id") == element.get("unitref")]
    if len(units) != 1 or normalized_text(units[0]) != "iso4217:USD":
        raise ValueError("NOT_USD_UNIT")
    value = fact_value(element)
    if value != Decimal(str(spec["expected_value_usd"])):
        raise ValueError("VALUE_CHANGED")
    return value * Decimal(str(spec["coefficient"]))


def verify_registry(registry, sources):
    cache, results = {}, []
    for item in registry["items"]:
        name = item["source_file"]
        if Path(name).name != name:
            raise ValueError("UNSAFE_SOURCE_PATH")
        path = sources / name
        if sha(path) != item["source_sha256"]:
            raise ValueError("SOURCE_HASH_MISMATCH")
        if name not in cache:
            cache[name] = html.fromstring(path.read_bytes())
        root = cache[name]
        value = sum((verify_fact(root, x, item["report_date"]) for x in item["components"]), Decimal(0))
        if not item["components"] or value != Decimal(str(item["expected_result_usd"])):
            raise ValueError("RECONCILIATION_TOTAL_MISMATCH")
        results.append({"item_id": item["item_id"], "ticker": item["ticker"], "field": item["field"],
                        "value_usd": str(value), "source_verification": "PASS",
                        "review_status": item["review_status"], "promoted_to_frozen_inputs": False})
    return {"schema": "r10f_source_corrections_verification_v1", "items": results,
            "source_verified_count": len(results), "case_closures": 0,
            "engine_modified": False, "ranking_recomputed": False, "system_live": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing receipt")
    result = verify_registry(json.loads(args.registry.read_text()), args.sources)
    result["registry_sha256"] = sha(args.registry)
    result["verifier_sha256"] = sha(Path(__file__))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "items"}, indent=2))


if __name__ == "__main__":
    main()
