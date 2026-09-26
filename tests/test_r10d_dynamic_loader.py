from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
R10D=ROOT/"src"/"r10d_real_overlays.py"

spec=importlib.util.spec_from_file_location("r10d_test",R10D)
mod=importlib.util.module_from_spec(spec)
sys.modules["r10d_test"]=mod
spec.loader.exec_module(mod)

market=mod.load("marketplace_classifier_r10d_test",ROOT/"src"/"marketplace_classifier_v42.py")
cash=mod.load("cash_quality_r10d_test",ROOT/"src"/"cash_quality_commitments_v42.py")

assert market.Evidence(source_type="PRIMARY",source_url_or_accession="x",filing_date="2026-01-01",
                       classification_as_of="2026-01-01",evidence_excerpt_or_hash="h").complete()
assert cash.ProvenancedAmount(value=1.0,status="PRESENT",source="s",data_as_of="2026-01-01",definition="d").usable()

print("R10D DYNAMIC DATACLASS IMPORT TEST PASSED")
