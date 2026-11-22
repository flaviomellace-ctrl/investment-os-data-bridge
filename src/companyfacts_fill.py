"""BRIDGE-2 companyfacts fill (R12-ter candidate, 2026-11-22). Research only.

Why: the SEC Financial Statement Data Sets carry only the face statements; ~25% of filers report the diluted
weighted share count (and some other items) only in the notes, so the bridge saw them as MISSING.
What: for each filing ALREADY selected by the unchanged bridge logic (point in time: filed <= as-of), add the
non-dimensional us-gaap facts that the SEC companyfacts API attributes to that same accession number, for the
same tags the bridge already reads. Strictly additive: a (adsh, tag, ddate, qtrs, uom) already present in the
data sets is never replaced. No other source, no later filing, no estimate.
"""
from __future__ import annotations

import gzip, json, os, time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

CACHE = Path(os.environ.get("PIT_CACHE", "/tmp/pit_fsds_cache")) / "companyfacts"
ADSH_CIK: dict[str, str] = {}
STATS = dict(ciks=0, http_errors=0, rows_added=0)
_LAST = [0.0]


def remember_submissions(sub: pd.DataFrame) -> None:
    for a, c in zip(sub["adsh"].astype(str), sub["cik"].astype(str)):
        ADSH_CIK[a] = str(int(float(c))).zfill(10) if c and c != "nan" else ""


def _facts(cik: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"CIK{cik}.json.gz"
    if f.exists():
        return json.loads(gzip.decompress(f.read_bytes()))
    wait = 0.15 - (time.time() - _LAST[0])
    if wait > 0:
        time.sleep(wait)
    _LAST[0] = time.time()
    email = os.environ.get("SEC_CONTACT_EMAIL", "research@example.com")
    r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                     headers={"User-Agent": f"InvestmentOS research {email}"}, timeout=120)
    if r.status_code != 200:
        STATS["http_errors"] += 1
        return {}
    STATS["ciks"] += 1
    f.write_bytes(gzip.compress(r.content))
    return r.json()


def fsds_ddate(end: str) -> str:
    """FSDS convention: ddate is the end date rounded to the nearest month end."""
    import calendar
    d = date.fromisoformat(end)
    last = calendar.monthrange(d.year, d.month)[1]
    if d.day >= 15:
        return f"{d.year:04d}{d.month:02d}{last:02d}"
    y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    return f"{y:04d}{m:02d}{calendar.monthrange(y, m)[1]:02d}"


def augment(nums: pd.DataFrame, adsh_set: set[str], tags: list[str]) -> pd.DataFrame:
    tagset = set(tags)
    have = set()
    if len(nums):
        have = set(zip(nums["adsh"].astype(str), nums["tag"].astype(str), nums["ddate"].astype(str).str[:8],
                       nums["qtrs"].astype(str), nums["uom"].astype(str).str.lower()))
    by_cik: dict[str, set[str]] = {}
    for a in adsh_set:
        c = ADSH_CIK.get(str(a), "")
        if c:
            by_cik.setdefault(c, set()).add(str(a))
    add = []
    for cik, accs in sorted(by_cik.items()):
        usg = _facts(cik).get("facts", {}).get("us-gaap", {})
        for tag in tagset & set(usg):
            for unit, vals in usg[tag].get("units", {}).items():
                for v in vals:
                    a = v.get("accn")
                    if a not in accs or v.get("val") is None or not v.get("end"):
                        continue
                    if v.get("start"):
                        days = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
                        qtrs = str(int(round(days / 91.3)))
                    else:
                        qtrs = "0"
                    ddate = fsds_ddate(v["end"])
                    key = (a, tag, ddate, qtrs, unit.lower())
                    if key in have:
                        continue
                    have.add(key)
                    add.append(dict(adsh=a, tag=tag, version="companyfacts", ddate=ddate, qtrs=qtrs, uom=unit,
                                    segments="", coreg="", value=str(v["val"]), footnote="",
                                    sec_source_quarter="companyfacts"))
    STATS["rows_added"] += len(add)
    if not add:
        return nums
    extra = pd.DataFrame(add)
    out = pd.concat([nums, extra], ignore_index=True, sort=False)
    for col, src in (("value_num", "value"), ("ddate_num", "ddate"), ("qtrs_num", "qtrs")):
        if col in nums.columns:
            out[col] = pd.to_numeric(out[src], errors="coerce")
    return out
