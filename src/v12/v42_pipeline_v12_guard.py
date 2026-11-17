#!/usr/bin/env python3
"""V4.2-INTEGRATED-1.2-CANDIDATE (shadow). Frozen 1.1 pipeline + one queue-eligibility guard.

Guard "deterioramento economico" (Costituzione par. 2: distinguere volatilita' da deterioramento economico;
par. 7 Temporary Mispricing richiede franchise intatta). It changes ONLY who may enter the 7+3 deep-dive
queue; BQS, IOS, formulas, thresholds, lanes and the Decision Gate are untouched. Names blocked by the guard
get the flag DETERIORATION_GUARD and stay out of the queue; the next eligible name backfills.

G1 operating income of the latest fiscal year below 90% of the prior year            -> blocked (both lanes)
G2 revenue of the latest fiscal year below 97% of the prior year                      -> blocked (both lanes)
G3 Lane I only: prior-year revenue growth above 10% and latest growth below half of it -> blocked
   (an inflection thesis needs growth that holds, not growth that is fading)
Missing inputs: Lane V not blocked (missing is not penalised, par. 5); Lane I blocked (the lane needs the data).
"""
import csv, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import inflection_lane_v42 as lane  # noqa: E402
import v42_integrated_pipeline as pipe  # noqa: E402

VERSION = "V4.2-INTEGRATED-1.2-CANDIDATE-SHADOW"


def f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def guard_table(candidate):
    out = {}
    with open(candidate, newline="") as fh:
        for r in csv.DictReader(fh):
            oi, poi = f(r.get("annual_operating_income")), f(r.get("prior_operating_income"))
            rv, prv, p2 = f(r.get("annual_revenue")), f(r.get("prior_revenue")), f(r.get("fy_minus_2_revenue"))
            g1 = None if oi is None or poi is None or poi <= 0 else oi < 0.90 * poi
            g2 = None if rv is None or prv is None or prv <= 0 else rv < 0.97 * prv
            gl = None if rv is None or prv is None or prv <= 0 else rv / prv - 1
            gp = None if prv is None or p2 is None or p2 <= 0 else prv / p2 - 1
            g3 = None if gl is None or gp is None else (gp > 0.10 and gl < 0.5 * gp)
            out[r["ticker"]] = dict(g1=g1, g2=g2, g3=g3)
    return out


def blocked(t, lane_name, G):
    g = G.get(t)
    if g is None:
        return lane_name == "I"
    if g["g1"] or g["g2"]:
        return True
    if lane_name == "I":
        return g["g3"] is None or g["g3"] or g["g1"] is None or g["g2"] is None
    return False


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cand = argv[argv.index("--candidate") + 1]
    G = guard_table(cand)
    orig = lane.merge_deep_dive_queue
    report = {"blocked": []}

    def guarded(lane_v, lane_i):
        v = [r for r in lane_v if not blocked(r["entity_key"], "V", G)]
        i = [r for r in lane_i if not blocked(r["entity_key"], "I", G)]
        report["blocked"] = sorted({r["entity_key"] for r in lane_v[:30] if blocked(r["entity_key"], "V", G)} |
                                   {r["entity_key"] for r in lane_i[:15] if blocked(r["entity_key"], "I", G)})
        return orig(v, i)

    lane.merge_deep_dive_queue = guarded
    pipe.lane.merge_deep_dive_queue = guarded
    rc = pipe.main(argv)
    out = Path(argv[argv.index("--out") + 1])
    import json
    (out / "v12_guard_report.json").write_text(json.dumps(dict(version=VERSION, blocked_near_top=report["blocked"]), indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
