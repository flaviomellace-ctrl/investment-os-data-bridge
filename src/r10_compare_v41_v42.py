#!/usr/bin/env python3
"""
Investment OS V4.2 — R10 historical V4.1 comparison.

FIRST REAL-DATA V4.2 ENGINE COMPARISON.
The engine, Lane-I thresholds and merge rule must already be frozen before this script runs.

Purpose:
- compare frozen V4.1 outputs with the frozen V4.2 numeric engine on the exact V4.1
  canonical fundamentals and exact V4.1 market snapshot;
- measure coverage/rank/distribution drift;
- exercise the frozen Lane-I rule on historical data as a diagnostic.

Non-purpose:
- no parameter tuning;
- no fresh market data;
- no documentary BR-09 marketplace reclassification;
- no real-data cash-quality/commitments enrichment;
- no BUY/ADD;
- no validation target is opened or used.

Any substantive result that is undesirable is evidence, not permission to modify V4.2 in-place.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

CANONICAL = ROOT / "data" / "current" / "sp500_fundamentals.csv"
V41_DIR = ROOT / "data" / "blind_v4_1" / "36045268572" / "quantitative"
V41_RANKING = V41_DIR / "V4_1_RANKING_FULL.csv"
V41_MARKET = V41_DIR / "V4_1_MARKET_SNAPSHOT.csv"
V41_RECEIPT = V41_DIR / "FREEZE_RECEIPT.json"

V42_ENGINE = ROOT / "src" / "investment_os" / "v4_2" / "v4_scoring.py"
V42_MANIFEST = ROOT / "docs" / "V4_2_ENGINE_MANIFEST.json"
LANE_I_PATH = ROOT / "src" / "inflection_lane_v42.py"

EXPECTED_CANONICAL_SHA256 = "d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45"
EXPECTED_V41_RANKING_SHA256 = "fe6aa604ca9529e2ffa53927581c509e213dc0d034072e6508a6c3ae0d1542b0"
EXPECTED_V41_MARKET_SHA256 = "8d446fcdc0c6715d75746433840962dfb163874c7daccca95cad945cfdc9552d"
EXPECTED_V42_ENGINE_SHA256 = "cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e"
EXPECTED_V42_ENGINE_MD5 = "232ac18be2ada2d3a6ef97b0d4308b7b"
EXPECTED_ROWS = 504

# Pre-registered diagnostic guardrails. They do NOT retune the model.
# Crossing one means "investigate the system", never "change the threshold after seeing names".
IOS_POOL_LOSS_MAJOR = 0.30
IOS_POOL_LOSS_CRITICAL = 0.50
LANE_I_BREADTH_MAJOR = 0.15
TOP20_OVERLAP_MAJOR_FLOOR = 0.25


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def num(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "nan", "None", "MISSING", "NA", "NOT_APPLICABLE", "CONFLICTING"):
        return None
    try:
        x = float(s)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def boolish(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def sentinel(v: Any, engine) -> Any:
    s = "" if v is None else str(v).strip()
    if s == "NOT_APPLICABLE":
        return engine.NA
    if s == "CONFLICTING":
        return engine.CONFLICTING
    return num(v)


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    xs = sorted(float(x) for x in values)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi-k) + xs[hi] * (k-lo)


def spearman_from_rank_pairs(pairs: Sequence[Tuple[float,float]]) -> Optional[float]:
    if len(pairs) < 2:
        return None
    xs = [float(a) for a,b in pairs]
    ys = [float(b) for a,b in pairs]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    vx = sum((x-mx)**2 for x in xs)
    vy = sum((y-my)**2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx*vy)


def main() -> int:
    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    out = ROOT / "data" / "v4_2" / "r10" / str(run_id)
    out.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ seals
    required = [CANONICAL, V41_RANKING, V41_MARKET, V41_RECEIPT, V42_ENGINE, V42_MANIFEST, LANE_I_PATH]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing required files: " + ", ".join(missing))

    checks: Dict[str,bool] = {}
    checks["canonical_sha"] = sha256_file(CANONICAL) == EXPECTED_CANONICAL_SHA256
    checks["v41_ranking_sha"] = sha256_file(V41_RANKING) == EXPECTED_V41_RANKING_SHA256
    checks["v41_market_sha"] = sha256_file(V41_MARKET) == EXPECTED_V41_MARKET_SHA256
    checks["v42_engine_sha"] = sha256_file(V42_ENGINE) == EXPECTED_V42_ENGINE_SHA256
    checks["v42_engine_md5"] = md5_file(V42_ENGINE) == EXPECTED_V42_ENGINE_MD5

    manifest = json.loads(V42_MANIFEST.read_text(encoding="utf-8"))
    checks["engine_manifest_frozen"] = manifest.get("frozen") is True
    checks["manifest_engine_sha"] = manifest.get("v4_2_engine_sha256") == EXPECTED_V42_ENGINE_SHA256
    checks["manifest_real_ranking_false_before_run"] = manifest.get("real_data_v42_ranking_executed") is False
    checks["manifest_bqs_unchanged"] = manifest.get("bqs_changed") is False
    checks["manifest_ios_weights_unchanged"] = manifest.get("ios_weights_changed") is False

    freeze_receipt = json.loads(V41_RECEIPT.read_text(encoding="utf-8"))
    checks["v41_receipt_canonical_sha"] = freeze_receipt.get("canonical_sha256") == EXPECTED_CANONICAL_SHA256

    if not all(checks.values()):
        failed = [k for k,v in checks.items() if not v]
        raise SystemExit("R10 pre-run seal failed: " + ", ".join(failed))

    engine = load_module("v42_engine_r10", V42_ENGINE)
    lane = load_module("lane_i_r10", LANE_I_PATH)

    canonical_rows = read_csv(CANONICAL)
    baseline_rows = read_csv(V41_RANKING)
    market_rows = read_csv(V41_MARKET)

    if len(canonical_rows) != EXPECTED_ROWS or len(baseline_rows) != EXPECTED_ROWS:
        raise SystemExit(f"Unexpected universe size canonical={len(canonical_rows)} baseline={len(baseline_rows)}")

    canon = {r["ticker"].strip(): r for r in canonical_rows}
    base = {r["ticker"].strip(): r for r in baseline_rows}
    market = {r["ticker"].strip(): r for r in market_rows}

    if set(canon) != set(base):
        raise SystemExit("Canonical vs V4.1 baseline ticker universe mismatch")

    # ---------------------------------------------------- V4.2 numeric engine
    v42_rows: List[Dict[str,Any]] = []
    lane_input: List[Dict[str,Any]] = []

    for ticker in sorted(base):
        br = base[ticker]
        cr = canon[ticker]
        mr = market.get(ticker, {})

        bqs_score = num(br.get("bqs"))
        bqs_cov = num(br.get("bqs_coverage_pct"))
        data_cov = num(br.get("data_coverage_pct")) or 0.0
        module = (br.get("module") or "GENERAL").strip() or "GENERAL"

        c: Dict[str,Any] = {
            "module": module,
            "data_coverage_pct": data_cov,
            "market_cap": num(br.get("market_cap")),
            "price": num(br.get("market_price")),
            "net_debt_to_ocf": sentinel(cr.get("net_debt_to_ocf"), engine),
            "book_value": num(cr.get("annual_equity")),
            "roe": num(cr.get("roe_simple")),
            "payout_ratio": num(cr.get("payout_ratio")),
            "combined_ratio": num(cr.get("combined_ratio")),
            "affo": num(cr.get("affo")),
            "revenue_cagr3": num(cr.get("revenue_cagr3")),
            "fcf_per_share_cagr3": num(cr.get("fcf_per_share_cagr3")),
            "share_change": num(cr.get("diluted_shares_yoy")),
            "ocf": num(cr.get("annual_operating_cash_flow")),
            "capex": num(cr.get("annual_capex")),
            "sbc": num(cr.get("annual_sbc")),
        }

        ios_score = None
        detail: Dict[str,Any] = {}
        if bqs_score is not None and bqs_cov is not None:
            ios_score, detail = engine.ios(c, bqs_score, bqs_cov)

        row = {
            "ticker": ticker,
            "name": br.get("name",""),
            "module_v41": module,
            "module_v42_r10": module,  # BR-09 documentary routing deliberately not applied in R10.
            "bqs_v41": bqs_score if bqs_score is not None else "",
            "bqs_v42": bqs_score if bqs_score is not None else "",
            "bqs_rank_v41": br.get("bqs_rank",""),
            "bqs_confidence": br.get("bqs_confidence",""),
            "metric_coverage_pct": br.get("metric_coverage_pct",""),
            "data_coverage_pct": br.get("data_coverage_pct",""),
            "market_price_frozen": br.get("market_price",""),
            "market_cap_frozen": br.get("market_cap",""),
            "market_source": br.get("market_source",""),
            "ios_v41": br.get("ios",""),
            "ios_rank_v41": br.get("ios_rank",""),
            "ios_variant_v41": br.get("ios_variant",""),
            "ios_v42": ios_score if ios_score is not None else "",
            "ios_rank_v42": "",
            "ios_variant_v42": detail.get("variant", engine.ios_variant(module)),
            "ios_gate_v42": detail.get("gate","") if ios_score is None else "",
            "growth_policy_v42": detail.get("growth_policy",""),
            "growth_used_v42": detail.get("growth_used",""),
            "dcf_growth_used_v42": detail.get("dcf_growth_used",""),
            "owner_yield_v42": detail.get("owner_yield",""),
            "expected_return_v42": detail.get("exp_ret",""),
            "margin_of_safety_v42": detail.get("mos",""),
            "bear_return_v42": detail.get("bear",""),
            "bull_return_v42": detail.get("bull",""),
            "ios_delta_v42_minus_v41": "",
        }
        v41_ios = num(br.get("ios"))
        if ios_score is not None and v41_ios is not None:
            row["ios_delta_v42_minus_v41"] = round(float(ios_score) - v41_ios, 4)
        v42_rows.append(row)

        # Lane-I historical diagnostic. Cash-quality documentary overlay is NOT complete here.
        ocf = num(cr.get("annual_operating_cash_flow"))
        capex = num(cr.get("annual_capex"))
        sbc = num(cr.get("annual_sbc"))
        ni = num(cr.get("annual_net_income"))
        owner = None if None in (ocf,capex,sbc) else ocf-capex-sbc
        cash_conv = (ocf/ni) if (ocf is not None and ni not in (None,0)) else None
        growth_flags = [x for x in (br.get("growth_flags") or "").split("|") if x]

        lane_input.append({
            "entity_key": ticker,
            "ticker": ticker,
            "name": br.get("name",""),
            "bqs": bqs_score,
            "owner_earnings": owner,
            "revenue_cagr3": num(cr.get("revenue_cagr3")),
            "fcf_cagr3": num(cr.get("fcf_cagr3")),
            "fcf_per_share_cagr3": num(cr.get("fcf_per_share_cagr3")),
            "cash_conversion": cash_conv,
            "share_change": num(cr.get("diluted_shares_yoy")),
            "growth_flags": growth_flags,
            "quality_flags": [],
            "cyclical_rebound_flag": False,
        })

    # Official V4.2 IOS rank for the historical comparison.
    numeric = [r for r in v42_rows if num(r.get("ios_v42")) is not None]
    numeric.sort(key=lambda r: (
        -float(r["ios_v42"]),
        -float(r["bqs_v42"]),
        r["ticker"],
    ))
    for i,r in enumerate(numeric,1):
        r["ios_rank_v42"] = i

    # -------------------------------------------------------------- Lane I
    lane_ranked = lane.rank_lane_i(lane_input)
    lane_rows = []
    for i,r in enumerate(lane_ranked,1):
        lane_rows.append({
            "lane_i_rank": i,
            "ticker": r["ticker"],
            "name": r["name"],
            "score": r["score"],
            "bqs": r["bqs"],
            "revenue_cagr3": r["revenue_cagr3"],
            "fcf_cagr3": r["fcf_cagr3"],
            "fcf_per_share_cagr3": r["fcf_per_share_cagr3"],
            "cash_conversion": r["cash_conversion"],
            "share_change": r["share_change"],
            "confidence": r["confidence"],
            "cash_quality_overlay_complete": False,
            "documentary_cyclical_review_complete": False,
            "status": "R10_PRE_DIAGNOSTIC_ONLY",
        })

    # Diagnostic 7+3 queue. Not authorized for forward qualitative use yet because
    # BR-09 and real-data quality/commitments overlays have not been completed.
    lane_v_for_merge = [
        {"entity_key":r["ticker"],"ticker":r["ticker"],"name":r["name"],
         "ios":r["ios_v42"],"bqs":r["bqs_v42"],"ios_rank":r["ios_rank_v42"]}
        for r in numeric
    ]
    lane_i_for_merge = [
        {"entity_key":r["ticker"],"ticker":r["ticker"],"name":r["name"],
         "score":r["score"],"bqs":r["bqs"]}
        for r in lane_rows
    ]
    merged = lane.merge_deep_dive_queue(lane_v_for_merge, lane_i_for_merge)
    merged_rows=[]
    for i,r in enumerate(merged,1):
        merged_rows.append({
            "queue_rank":i,
            "ticker":r.get("ticker",r.get("entity_key","")),
            "name":r.get("name",""),
            "selection_lane":r.get("selection_lane",""),
            "ios":r.get("ios",""),
            "inflection_score":r.get("score",""),
            "bqs":r.get("bqs",""),
            "status":"R10_DIAGNOSTIC_QUEUE_NOT_FORWARD_AUTHORIZED",
        })

    # ------------------------------------------------------------- aggregates
    v41_numeric = [r for r in baseline_rows if num(r.get("ios")) is not None]
    v42_numeric = numeric
    matched = []
    v42_by = {r["ticker"]:r for r in v42_rows}
    for br in baseline_rows:
        i41 = num(br.get("ios"))
        i42 = num(v42_by[br["ticker"]].get("ios_v42"))
        if i41 is not None and i42 is not None:
            matched.append((br["ticker"],i41,i42))

    deltas = [b-a for _,a,b in matched]
    blocked = [
        v42_by[br["ticker"]]
        for br in baseline_rows
        if num(br.get("ios")) is not None and num(v42_by[br["ticker"]].get("ios_v42")) is None
    ]
    blocked_reasons = Counter(r["ios_gate_v42"] or "UNKNOWN" for r in blocked)

    top20_v41 = [r["ticker"] for r in sorted(
        v41_numeric, key=lambda r:int(float(r["ios_rank"] or 999999))
    )[:20]]
    top20_v42 = [r["ticker"] for r in numeric[:20]]
    overlap20 = len(set(top20_v41)&set(top20_v42))
    jaccard20 = overlap20 / len(set(top20_v41)|set(top20_v42)) if (top20_v41 or top20_v42) else None

    top10_v41 = top20_v41[:10]
    top10_v42 = top20_v42[:10]
    overlap10 = len(set(top10_v41)&set(top10_v42))

    rank_pairs=[]
    for t,_,_ in matched:
        r41=num(base[t].get("ios_rank"))
        r42=num(v42_by[t].get("ios_rank_v42"))
        if r41 is not None and r42 is not None:
            rank_pairs.append((r41,r42))
    rho=spearman_from_rank_pairs(rank_pairs)

    bqs_gate_pool = sum(
        1 for r in baseline_rows
        if num(r.get("bqs")) is not None and num(r.get("bqs")) >= 60
        and (num(r.get("data_coverage_pct")) or 0) >= 70
    )
    lane_breadth = (len(lane_rows)/bqs_gate_pool) if bqs_gate_pool else None
    pool_loss = (
        (len(v41_numeric)-len(v42_numeric))/len(v41_numeric)
        if v41_numeric else None
    )

    alerts=[]
    severity="PASS_INTEGRITY"
    if pool_loss is not None and pool_loss > IOS_POOL_LOSS_CRITICAL:
        alerts.append("CRITICAL_IOS_NUMERIC_POOL_LOSS")
        severity="CRITICAL_REVIEW"
    elif pool_loss is not None and pool_loss > IOS_POOL_LOSS_MAJOR:
        alerts.append("MAJOR_IOS_NUMERIC_POOL_LOSS")
        severity="MAJOR_REVIEW"

    if lane_breadth is not None and lane_breadth > LANE_I_BREADTH_MAJOR:
        alerts.append("MAJOR_LANE_I_TOO_BROAD")
        if severity=="PASS_INTEGRITY":
            severity="MAJOR_REVIEW"

    if len(top20_v41)==20 and len(top20_v42)==20 and overlap20/20 < TOP20_OVERLAP_MAJOR_FLOOR:
        alerts.append("MAJOR_TOP20_RANK_INSTABILITY")
        if severity=="PASS_INTEGRITY":
            severity="MAJOR_REVIEW"

    module_stats=defaultdict(lambda: {
        "universe":0,"v41_ios_numeric":0,"v42_ios_numeric":0,"matched":0,"delta_sum":0.0
    })
    for br in baseline_rows:
        mod=br.get("module","")
        s=module_stats[mod]; s["universe"]+=1
        i41=num(br.get("ios")); i42=num(v42_by[br["ticker"]].get("ios_v42"))
        if i41 is not None: s["v41_ios_numeric"]+=1
        if i42 is not None: s["v42_ios_numeric"]+=1
        if i41 is not None and i42 is not None:
            s["matched"]+=1; s["delta_sum"] += i42-i41
    for mod,s in module_stats.items():
        s["mean_ios_delta_matched"] = round(s["delta_sum"]/s["matched"],4) if s["matched"] else None
        del s["delta_sum"]

    agg = {
        "schema":"investment_os_v4_2_r10_aggregates_v1.0",
        "run_id":run_id,
        "scope":"HISTORICAL_ENGINE_AND_DISCOVERY_NUMERIC_COMPARISON",
        "system_live":False,
        "real_data_v42_ranking_executed":True,
        "fresh_market_data_used":False,
        "frozen_v41_market_snapshot_used":True,
        "marketplace_documentary_routing_applied":False,
        "cash_quality_real_overlay_complete":False,
        "commitments_real_overlay_complete":False,
        "universe_rows":len(baseline_rows),
        "bqs_gate_pool":bqs_gate_pool,
        "v41_ios_numeric":len(v41_numeric),
        "v42_ios_numeric":len(v42_numeric),
        "ios_pool_loss_fraction":round(pool_loss,6) if pool_loss is not None else None,
        "matched_numeric":len(matched),
        "ios_delta_matched":{
            "mean":round(statistics.mean(deltas),4) if deltas else None,
            "median":round(statistics.median(deltas),4) if deltas else None,
            "p05":round(percentile(deltas,.05),4) if deltas else None,
            "p95":round(percentile(deltas,.95),4) if deltas else None,
            "min":round(min(deltas),4) if deltas else None,
            "max":round(max(deltas),4) if deltas else None,
        },
        "v41_numeric_to_v42_blocked":len(blocked),
        "blocked_reasons":dict(sorted(blocked_reasons.items())),
        "top20_overlap_count":overlap20,
        "top20_jaccard":round(jaccard20,6) if jaccard20 is not None else None,
        "top10_overlap_count":overlap10,
        "spearman_common_numeric":round(rho,6) if rho is not None else None,
        "lane_i_pre_diagnostic_count":len(lane_rows),
        "lane_i_breadth_fraction":round(lane_breadth,6) if lane_breadth is not None else None,
        "diagnostic_queue_count":len(merged_rows),
        "module_stats":dict(sorted(module_stats.items())),
        "alerts":alerts,
        "review_status":severity,
    }

    # --------------------------------------------------------------- outputs
    comparison_fields=[
        "ticker","name","module_v41","module_v42_r10",
        "bqs_v41","bqs_v42","bqs_rank_v41","bqs_confidence",
        "metric_coverage_pct","data_coverage_pct",
        "market_price_frozen","market_cap_frozen","market_source",
        "ios_v41","ios_rank_v41","ios_variant_v41",
        "ios_v42","ios_rank_v42","ios_variant_v42","ios_gate_v42",
        "ios_delta_v42_minus_v41",
        "growth_policy_v42","growth_used_v42","dcf_growth_used_v42",
        "owner_yield_v42","expected_return_v42","margin_of_safety_v42",
        "bear_return_v42","bull_return_v42",
    ]
    write_csv(out/"V4_2_R10_FULL_COMPARISON.csv",
              sorted(v42_rows,key=lambda r:r["ticker"]), comparison_fields)
    write_csv(out/"V4_2_R10_LANE_I_PRE_DIAGNOSTIC.csv", lane_rows, [
        "lane_i_rank","ticker","name","score","bqs","revenue_cagr3","fcf_cagr3",
        "fcf_per_share_cagr3","cash_conversion","share_change","confidence",
        "cash_quality_overlay_complete","documentary_cyclical_review_complete","status"
    ])
    write_csv(out/"V4_2_R10_DIAGNOSTIC_QUEUE.csv", merged_rows, [
        "queue_rank","ticker","name","selection_lane","ios","inflection_score","bqs","status"
    ])
    (out/"V4_2_R10_AGGREGATES.json").write_text(
        json.dumps(agg,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"
    )

    # No ticker-specific conclusion in the report. Names live in CSV evidence only.
    report = f"""# Investment OS V4.2 — R10 Historical V4.1 Comparison

**FIRST REAL-DATA V4.2 ENGINE COMPARISON — FROZEN RULES, NO POST-RESULT TUNING**

- Run: **{run_id}**
- System: **NOT LIVE**
- Universe: **{len(baseline_rows)}**
- Canonical SHA-256: `{EXPECTED_CANONICAL_SHA256}`
- V4.1 ranking SHA-256: `{EXPECTED_V41_RANKING_SHA256}`
- Frozen market snapshot SHA-256: `{EXPECTED_V41_MARKET_SHA256}`
- V4.2 engine SHA-256: `{EXPECTED_V42_ENGINE_SHA256}`
- Fresh market data: **NO**
- Validation target used: **NO**
- BR-09 documentary marketplace routing applied: **NO**
- Real cash-quality / commitments overlay complete: **NO**

## Aggregate result

- V4.1 IOS numeric: **{len(v41_numeric)}**
- V4.2 IOS numeric: **{len(v42_numeric)}**
- Previously numeric now blocked: **{len(blocked)}**
- Matched numeric: **{len(matched)}**
- Median IOS delta on matched rows: **{agg['ios_delta_matched']['median']}**
- P05 / P95 IOS delta: **{agg['ios_delta_matched']['p05']} / {agg['ios_delta_matched']['p95']}**
- Top-20 overlap: **{overlap20}/20**
- Top-10 overlap: **{overlap10}/10**
- Spearman on common numeric ranks: **{agg['spearman_common_numeric']}**
- Lane-I pre-diagnostic candidates: **{len(lane_rows)}**
- Diagnostic merged queue: **{len(merged_rows)}**
- Review status: **{severity}**
- Alerts: **{', '.join(alerts) if alerts else 'none'}**

## Interpretation boundary

R10 measures engine/discovery drift only. It is **not** the final V4.2 blind result and
does not authorize qualitative use of the diagnostic queue.

The following mandatory V4.2 layers still require real-data completion before a new
blind/forward validation:
1. BR-09 documentary marketplace routing/enrichment;
2. real cash-quality diagnostic overlay for advancing candidates;
3. real off-balance commitments review for advancing candidates.

No formula, threshold, lane quota or tie-break may be modified after this run merely
because of the companies or ranks observed. A substantive model change requires a new
version/change-control cycle.

**System remains NOT LIVE.**
"""
    (out/"V4_2_R10_REPORT.md").write_text(report,encoding="utf-8")

    output_names=[
        "V4_2_R10_FULL_COMPARISON.csv",
        "V4_2_R10_LANE_I_PRE_DIAGNOSTIC.csv",
        "V4_2_R10_DIAGNOSTIC_QUEUE.csv",
        "V4_2_R10_AGGREGATES.json",
        "V4_2_R10_REPORT.md",
    ]
    output_hashes={
        name:{"sha256":sha256_file(out/name),"bytes":(out/name).stat().st_size}
        for name in output_names
    }
    receipt={
        "schema":"investment_os_v4_2_r10_receipt_v1.0",
        "stage":"R10_HISTORICAL_V41_COMPARISON",
        "run_id":run_id,
        "frozen":True,
        "system_live":False,
        "real_data_v42_ranking_executed":True,
        "post_result_tuning_authorized":False,
        "fresh_market_data_used":False,
        "validation_material_used":False,
        "canonical_sha256":EXPECTED_CANONICAL_SHA256,
        "v41_ranking_sha256":EXPECTED_V41_RANKING_SHA256,
        "v41_market_snapshot_sha256":EXPECTED_V41_MARKET_SHA256,
        "v42_engine_sha256":EXPECTED_V42_ENGINE_SHA256,
        "v42_engine_md5":EXPECTED_V42_ENGINE_MD5,
        "pre_run_checks":checks,
        "aggregate_review_status":severity,
        "alerts":alerts,
        "marketplace_documentary_routing_applied":False,
        "cash_quality_real_overlay_complete":False,
        "commitments_real_overlay_complete":False,
        "outputs":output_hashes,
        "next_gate":"REAL_DATA_OVERLAYS_BR09_R6_R7_BEFORE_NEW_BLIND_VALIDATION",
    }
    (out/"V4_2_R10_RECEIPT.json").write_text(
        json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"
    )

    print("V4.2 R10 HISTORICAL COMPARISON COMPLETE")
    print("output_dir =", out.relative_to(ROOT))
    print("review_status =", severity)
    print("universe =", len(baseline_rows))
    print("v41_ios_numeric =", len(v41_numeric))
    print("v42_ios_numeric =", len(v42_numeric))
    print("matched_numeric =", len(matched))
    print("lane_i_pre_diagnostic =", len(lane_rows))
    print("top20_overlap =", overlap20)
    print("alerts =", alerts)
    print("SYSTEM LIVE = NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
