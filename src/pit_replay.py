#!/usr/bin/env python3
"""Point-in-time replay harness for the data bridge. Research / validation only.

Runs the UNMODIFIED bridge stages as they would have run on a past date:
- only SEC Financial Statement Data Sets of quarters <= the as-of quarter are visible;
- only filings with `filed` <= PIT_AS_OF are visible;
- the universe is an explicit file (ticker, ticker_sec, name, sector, weight, cik), never today's index.
It must be executed from a scratch copy of the repository so that data/current of the real repo is untouched.
"""
from __future__ import annotations

import hashlib, json, os, shutil, sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AS_OF = int(os.environ["PIT_AS_OF"])
UNIVERSE = Path(os.environ["PIT_UNIVERSE"])
STAGES = os.environ.get("PIT_STAGES", "bridge,br0102,br03").split(",")
CACHE = Path(os.environ.get("PIT_CACHE", "/tmp/pit_fsds_cache"))
if (ROOT / ".git").exists() and os.environ.get("PIT_ALLOW_REPO_ROOT") != "1":
    raise SystemExit("PIT_BLOCK: run from a scratch copy, not from the repository root")

sys.path.insert(0, str(HERE))
import bridge  # noqa: E402

_discover, _load_subs, _download = bridge.discover_sec_quarters, bridge.load_submissions_from_zips, bridge.download_to_file


def discover(d):
    quarters, meta = _discover(d)
    limit = (AS_OF // 10000, (AS_OF // 100 % 100 - 1) // 3 + 1)
    kept = [q for q in quarters if (q.year, q.quarter) <= limit]
    if not kept:
        raise SystemExit("PIT_BLOCK: no SEC dataset at or before the as-of date")
    return kept, dict(meta, latest_available=kept[-1].key, quarters_found=len(kept), pit_as_of=AS_OF)


def load_subs(zip_infos):
    sub = _load_subs(zip_infos)
    keep = pd.to_numeric(sub["filed"], errors="coerce") <= AS_OF
    print(f"PIT: submissions visible {int(keep.sum())}/{len(sub)} (filed <= {AS_OF})")
    return sub[keep].copy()


def download(d, url, path):
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not cached.exists():
        tmp = cached.with_suffix(".part")
        sha, n = _download(d, url, tmp)
        tmp.rename(cached)
    shutil.copyfile(cached, path)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), Path(path).stat().st_size


def universe_frame():
    df = pd.read_csv(UNIVERSE, dtype=str).fillna("")
    df["cik"] = df["cik"].map(lambda x: str(int(float(x))).zfill(10) if x else "")
    return df


def state_street(d):
    df = universe_frame()
    cols = [c for c in ("ticker", "ticker_sec", "name", "sector", "weight", "identifier", "isin", "asset_class") if c in df.columns]
    meta = dict(source="PIT explicit universe file", data_as_of=str(AS_OF), sha256=hashlib.sha256(UNIVERSE.read_bytes()).hexdigest(),
                equity_like_rows=int(len(df)))
    return df[cols].copy(), meta


def ticker_map(d):
    df = universe_frame()
    df = df[df["cik"].ne("")]
    out = pd.DataFrame(dict(ticker_sec=df["ticker_sec"], cik=df["cik"], sec_title=df.get("sec_title", df["name"])))
    return out.drop_duplicates("ticker_sec"), dict(source="PIT explicit universe file", rows=int(len(out)))


bridge.discover_sec_quarters, bridge.load_submissions_from_zips, bridge.download_to_file = discover, load_subs, download
bridge.download_state_street, bridge.download_sec_ticker_map = state_street, ticker_map

if "bridge" in STAGES:
    bridge.refresh("full", 4, True)
if "br0102" in STAGES:
    import enrich_br01_br02
    rc = enrich_br01_br02.main()
    if rc:
        raise SystemExit(f"PIT_BLOCK: BR-01/02 rc={rc}")
if "br03" in STAGES:
    import enrich_br03_capital_return
    rc = enrich_br03_capital_return.main()
    if rc:
        raise SystemExit(f"PIT_BLOCK: BR-03 rc={rc}")
out = ROOT / "data" / "current" / "sp500_fundamentals.csv"
print("PIT_REPLAY=" + json.dumps(dict(as_of=AS_OF, stages=STAGES, rows=int(len(pd.read_csv(out, low_memory=False))),
                                      fundamentals_sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
