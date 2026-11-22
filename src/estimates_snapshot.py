#!/usr/bin/env python3
"""
Archivio point-in-time delle stime degli analisti, costruito gratis da oggi in avanti.

Perché: i professionisti usano lo storico delle stime (I/B/E/S, FactSet) per vedere quando il consenso
taglia le previsioni prima che i bilanci lo mostrino. Quello storico costa decine di migliaia di euro.
Non si può comprare il passato, ma si può registrare il futuro: ogni giorno feriale questo script salva
la fotografia delle stime correnti per tutto l'S&P 500, con data. Fra 30-90 giorni l'archivio permette
di misurare le revisioni; fra 1-2 anni diventa un dataset point-in-time proprio.

Fonte: API pubblica Nasdaq (stime di consenso Zacks mostrate su nasdaq.com): earnings-forecast e targetprice.
Scrive:
- data/estimates/AAAA-MM-GG.csv  fotografia del giorno (append-only: un file per giorno, mai riscritto)
- data/current/estimates_latest.csv
- data/current/estimate_revisions.csv  variazione del consenso EPS dell'anno in corso e del prossimo rispetto
  alla fotografia più vicina a 30 e 90 giorni prima (vuota finché l'archivio non ha quella profondità)
Dati mancanti: vuoti con stato MISSING, mai zero.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data" / "current" / "sp500_universe.csv"
EXTRA = ROOT / "data" / "watchlist_tickers.txt"
ARCH = ROOT / "data" / "estimates"
CUR = ROOT / "data" / "current"
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                  "Accept": "application/json, text/plain, */*", "Referer": "https://www.nasdaq.com/"})
FIELDS = ["ticker", "snapshot_date", "fy0_end", "fy0_eps", "fy0_n", "fy0_high", "fy0_low", "fy1_end", "fy1_eps",
          "fy1_n", "q0_end", "q0_eps", "q0_n", "target_mean", "target_high", "target_low", "rating", "status"]


LAST_ERR = {}


def get(url):
    for a in range(2):
        try:
            r = S.get(url, timeout=12)
            if r.status_code == 200:
                return r.json()
            LAST_ERR["e"] = f"HTTP {r.status_code}"
        except Exception as exc:
            LAST_ERR["e"] = type(exc).__name__
        time.sleep(1 + a)
    return None


def num(x):
    if x in (None, "", "N/A", "--"):
        return ""
    try:
        return float(str(x).replace("$", "").replace(",", ""))
    except ValueError:
        return ""


def snap(sym):
    row = {"ticker": sym, "snapshot_date": dt.date.today().isoformat()}
    q = sym.replace(".", "/")
    f = get(f"https://api.nasdaq.com/api/analyst/{q}/earnings-forecast")
    d = (f or {}).get("data") or {}
    yr = ((d.get("yearlyForecast") or {}).get("rows")) or []
    qt = ((d.get("quarterlyForecast") or {}).get("rows")) or []
    for i, key in ((0, "fy0"), (1, "fy1")):
        if len(yr) > i:
            r = yr[i]
            row[f"{key}_end"] = r.get("fiscalEnd", "")
            row[f"{key}_eps"] = num(r.get("consensusEPSForecast"))
            row[f"{key}_n"] = num(r.get("noOfEstimates"))
            if key == "fy0":
                row["fy0_high"], row["fy0_low"] = num(r.get("highEPSForecast")), num(r.get("lowEPSForecast"))
    if qt:
        row["q0_end"], row["q0_eps"], row["q0_n"] = (qt[0].get("fiscalEnd", ""), num(qt[0].get("consensusEPSForecast")),
                                                     num(qt[0].get("noOfEstimates")))
    t = get(f"https://api.nasdaq.com/api/analyst/{q}/targetprice")
    td = (t or {}).get("data") or {}
    c = td.get("consensusOverview") or {}
    row["target_mean"], row["target_high"], row["target_low"] = (num(c.get("priceTarget")), num(c.get("highPriceTarget")),
                                                                 num(c.get("lowPriceTarget")))
    row["rating"] = (c.get("buy") is not None and f"buy {c.get('buy')}/hold {c.get('hold')}/sell {c.get('sell')}") or ""
    row["status"] = "PRESENT" if row.get("fy0_eps") not in (None, "") else "MISSING"
    return row


def nearest(days_back):
    target = dt.date.today() - dt.timedelta(days=days_back)
    files = sorted(ARCH.glob("*.csv"))
    best = None
    for p in files:
        d = dt.date.fromisoformat(p.stem)
        if d <= target:
            best = p
    if best and (target - dt.date.fromisoformat(best.stem)).days <= 10:
        return best
    return None


def main() -> int:
    tick = [r["ticker"].strip().upper() for r in csv.DictReader(open(UNIVERSE)) if r.get("ticker")]
    extra = [t.strip().upper() for t in EXTRA.read_text().splitlines() if t.strip() and not t.startswith("#")]
    tick = list(dict.fromkeys(extra + tick))
    lim = int(os.getenv("EST_LIMIT", "0") or 0)
    if lim:
        tick = tick[:lim]
    from concurrent.futures import ThreadPoolExecutor
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, row in enumerate(ex.map(snap, tick)):
            rows.append(row)
            if i % 25 == 0 or lim:
                print(i, row["ticker"], row["status"], row.get("fy0_eps", ""), LAST_ERR.get("e", ""), flush=True)
    if not any(r["status"] == "PRESENT" for r in rows):
        print("Fonte non raggiungibile: nessuna stima", LAST_ERR, flush=True)
        return 1
    if lim:
        return 0
    ARCH.mkdir(parents=True, exist_ok=True)
    today = ARCH / f"{dt.date.today().isoformat()}.csv"
    if not today.exists():
        with open(today, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)
    with open(CUR / "estimates_latest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)
    rev = []
    old = {}
    for lab, back in (("30d", 30), ("90d", 90)):
        p = nearest(back)
        old[lab] = ({r["ticker"]: r for r in csv.DictReader(open(p))}, p.stem) if p else ({}, "")
    for r in rows:
        out = {"ticker": r["ticker"], "fy0_end": r.get("fy0_end", ""), "fy0_eps": r.get("fy0_eps", ""),
               "fy1_eps": r.get("fy1_eps", "")}
        for lab in ("30d", "90d"):
            o, d = old[lab]
            out[f"base_{lab}"] = d
            prev = o.get(r["ticker"])
            for k in ("fy0", "fy1"):
                val = ""
                if prev and prev.get(f"{k}_end") == r.get(f"{k}_end") and prev.get(f"{k}_eps") not in ("", None) \
                        and r.get(f"{k}_eps") not in ("", None):
                    a, b = float(r[f"{k}_eps"]), float(prev[f"{k}_eps"])
                    if b > 0:
                        val = f"{(a / b - 1) * 100:.1f}"
                out[f"{k}_eps_rev_{lab}_pct"] = val
        rev.append(out)
    with open(CUR / "estimate_revisions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rev[0].keys()))
        w.writeheader()
        w.writerows(rev)
    ok = sum(1 for r in rows if r["status"] == "PRESENT")
    print(f"PRESENT {ok}/{len(rows)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
