#!/usr/bin/env python3
"""Point-in-time S&P 500 universe (research only).

Starts from the current constituent table and undoes every documented change with an
effective date AFTER the as-of date (added -> removed, removed -> re-added).
Source: Wikipedia "List of S&P 500 companies" (current table + selected changes table).
Known limits are written to the report: the changes table is not guaranteed complete,
and re-added companies have no CIK here (resolved later from SEC filings filed <= as-of).
"""
from __future__ import annotations

import hashlib, io, json, os, sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def norm(t: str) -> str:
    return str(t or "").strip().upper()


def flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(dict.fromkeys(str(x) for x in c if "Unnamed" not in str(x))).strip() for c in df.columns]
    return df


def main(as_of: int, out: Path) -> dict:
    r = requests.get(URL, headers={"User-Agent": "InvestmentOS-research/1.0 (personal research)"}, timeout=60)
    r.raise_for_status()
    raw = r.content
    tables = pd.read_html(io.StringIO(r.text))
    cur = flatten(tables[0])
    chg = flatten(tables[1])
    sym = next(c for c in cur.columns if c.lower().startswith("symbol"))
    sec = next(c for c in cur.columns if c.lower().startswith("security"))
    sector = next((c for c in cur.columns if "sector" in c.lower()), None)
    cikc = next((c for c in cur.columns if c.upper() == "CIK"), None)
    members = {}
    for _, x in cur.iterrows():
        members[norm(x[sym])] = dict(name=str(x[sec]), sector=str(x[sector]) if sector else "",
                                     cik=str(int(x[cikc])).zfill(10) if cikc and pd.notna(x[cikc]) else "", origin="current")
    dcol = next(c for c in chg.columns if "date" in c.lower())
    at = next(c for c in chg.columns if c.lower().startswith("added") and "ticker" in c.lower())
    asec = next(c for c in chg.columns if c.lower().startswith("added") and "security" in c.lower())
    rt = next(c for c in chg.columns if c.lower().startswith("removed") and "ticker" in c.lower())
    rsec = next(c for c in chg.columns if c.lower().startswith("removed") and "security" in c.lower())
    undone, unparsed, conflicts = 0, 0, []
    rows = []
    for _, x in chg.iterrows():
        try:
            d = int(pd.to_datetime(str(x[dcol]), errors="raise").strftime("%Y%m%d"))
        except Exception:
            unparsed += 1
            continue
        rows.append((d, x))
    for d, x in sorted(rows, key=lambda z: -z[0]):  # newest first
        if d <= as_of:
            continue
        a, rm = norm(x[at]) if pd.notna(x[at]) else "", norm(x[rt]) if pd.notna(x[rt]) else ""
        if a:
            if a in members:
                members.pop(a)
            else:
                conflicts.append(f"{d}:added {a} not present")
        if rm:
            if rm in members:
                conflicts.append(f"{d}:removed {rm} already present")
            else:
                members[rm] = dict(name=str(x[rsec]) if pd.notna(x[rsec]) else rm, sector="", cik="", origin=f"readded_{d}")
        undone += 1
    df = pd.DataFrame([dict(ticker=t, ticker_sec=t.replace(".", "-"), name=v["name"], sector=v["sector"], weight="",
                            identifier="", isin="", asset_class="", cik=v["cik"], sec_title=v["name"], origin=v["origin"])
                       for t, v in sorted(members.items())])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    rep = dict(schema="pit_universe_v1", as_of=as_of, source=URL, source_sha256=hashlib.sha256(raw).hexdigest(),
               retrieved_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z", members=len(df),
               current_members=len(cur), changes_undone=undone, change_rows_unparsed=unparsed,
               readded_without_cik=int(((df["cik"] == "") & df["origin"].str.startswith("readded")).sum()),
               conflicts=conflicts[:50], conflict_count=len(conflicts),
               limits="Wikipedia changes table may be incomplete; universe is an approximation of point-in-time membership.")
    out.with_suffix(".json").write_text(json.dumps(rep, indent=1))
    print("PIT_UNIVERSE=" + json.dumps({k: rep[k] for k in ("as_of", "members", "changes_undone", "readded_without_cik", "conflict_count")}))
    return rep


if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]))
