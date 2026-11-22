#!/usr/bin/env python3
"""
Campanelli d'allarme gratuiti (EARLY WARNING v1.0, approvato da Flavio il 22/11/2026).

Per ogni titolo di data/watchlist_tickers.txt (portafoglio, lista d'attesa, coda):
1. Trimestrali SEC (companyfacts): ultimo trimestre contro lo stesso trimestre dell'anno prima,
   e somma degli ultimi 4 trimestri (TTM) contro i 4 precedenti, per ricavi, utile operativo, utile netto.
2. 8-K degli ultimi 30 giorni con le voci (items) dichiarate.
3. Form 4 degli ultimi 90 giorni: acquisti (codice P) e vendite (codice S) sul mercato dei dirigenti, in USD.
4. Short interest (API pubblica Nasdaq): ultimo dato e variazione rispetto a circa un mese prima.

Soglie fisse v1.0 (non si cambiano senza approvazione):
- TRIM_DETERIORO: utile operativo (o utile netto se manca) ultimo trimestre < -20% sull'anno prima,
  oppure TTM < -10% sul TTM precedente.
- RICAVI_GIU: ricavi TTM < -3% sul TTM precedente.
- 8K_ROSSO: voce 4.02 (bilanci non più affidabili), 1.03 (fallimento), 4.01 (cambio revisore).
- 8K_ATTENZIONE: voce 2.05 (ristrutturazione), 2.06 (svalutazioni), 5.02 (uscita/nomina dirigenti).
- INSIDER_VENDITE: vendite discrezionali sul mercato (escluse quelle dichiarate in piani 10b5-1) > 5 milioni USD
  e nessun acquisto in 90 giorni.
- SHORT_SU: short interest +30% o più rispetto a circa un mese prima.

I segnali sono campanelli: GIALLO -> INVESTIGARE. Non cambiano BQS, IOS, coda o soglie.
Dati mancanti restano vuoti con stato MISSING, mai zero.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "current"
TICKERS = ROOT / "data" / "watchlist_tickers.txt"
EMAIL = os.getenv("SEC_CONTACT_EMAIL", "").strip()
SEC = requests.Session()
SEC.headers.update({"User-Agent": f"InvestmentOSDataBridge/1.0 {EMAIL}" if EMAIL else
                    "InvestmentOSDataBridge/1.0 contact-missing", "Accept-Encoding": "gzip, deflate"})
NQ = requests.Session()
NQ.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                 "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                   "Accept": "application/json, text/plain, */*", "Referer": "https://www.nasdaq.com/"})
TODAY = dt.date.today()

REV_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
            "RevenuesNetOfInterestExpense", "InterestAndDividendIncomeOperating"]
OPI_TAGS = ["OperatingIncomeLoss"]
NI_TAGS = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]


def get(sess, url, **kw):
    for a in range(3):
        try:
            r = sess.get(url, timeout=30, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404):
                return None
        except Exception:
            pass
        time.sleep(1.5 + 2 * a)
    return None


def cik_map():
    r = get(SEC, "https://www.sec.gov/files/company_tickers.json")
    m = {}
    if r:
        for v in r.json().values():
            m[v["ticker"].upper()] = int(v["cik_str"])
    return m


def days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def quarters(facts, tags):
    """Serie trimestrale (end -> valore) dal tag con il dato più recente; Q4 = FY - 9 mesi stessa partenza.
    A parità di periodo vale il dato depositato per ultimo (eventuali riesposizioni)."""
    g = (facts.get("facts") or {}).get("us-gaap") or {}
    best = (None, [])
    for tag in tags:
        rows = ((g.get(tag) or {}).get("units") or {}).get("USD") or []
        q, fy, ytd9 = {}, {}, {}
        for x in rows:
            if x.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A") or "start" not in x:
                continue
            d = days(x["start"], x["end"])
            key, tgt = None, None
            if 80 <= d <= 100:
                key, tgt = x["end"], q
            elif 350 <= d <= 380:
                key, tgt = (x["start"], x["end"]), fy
            elif 260 <= d <= 285:
                key, tgt = (x["start"], x["end"]), ytd9
            if tgt is None:
                continue
            if key not in tgt or x.get("filed", "") >= tgt[key][1]:
                tgt[key] = (x["val"], x.get("filed", ""))
        q = {k: v[0] for k, v in q.items()}
        for (s0, e), (v, _) in fy.items():
            if e in q:
                continue
            for (s9, e9), (v9, _) in ytd9.items():
                if s9 == s0 and 80 <= days(e9, e) <= 100:
                    q[e] = v - v9
                    break
        series = sorted(q.items())
        if len(series) >= 5 and (best[0] is None or series[-1][0] > best[1][-1][0]):
            best = (tag, series)
    return best


def consecutive(qs):
    return all(80 <= days(a[0], b[0]) <= 100 for a, b in zip(qs, qs[1:]))


def yoy_last(qs):
    if len(qs) < 5:
        return None
    e, v = qs[-1]
    if (TODAY - dt.date.fromisoformat(e)).days > 200:
        return None
    for e0, v0 in reversed(qs[:-1]):
        if 350 <= days(e0, e) <= 380:
            return (v / v0 - 1) * 100 if v0 > 0 else None
    return None


def ttm_yoy(qs):
    if len(qs) < 8:
        return None
    last8 = qs[-8:]
    if not consecutive(last8) or (TODAY - dt.date.fromisoformat(last8[-1][0])).days > 200:
        return None
    a = sum(v for _, v in last8[4:])
    b = sum(v for _, v in last8[:4])
    return (a / b - 1) * 100 if b > 0 else None


def form4(cik, sub):
    rec = (sub.get("filings") or {}).get("recent") or {}
    buys = sells = planned = 0.0
    n = 0
    for form, date, acc, doc in zip(rec.get("form", []), rec.get("filingDate", []),
                                    rec.get("accessionNumber", []), rec.get("primaryDocument", [])):
        if form != "4" or (TODAY - dt.date.fromisoformat(date)).days > 90:
            continue
        if n >= 40:
            break
        n += 1
        raw = doc.split("/")[-1]
        r = get(SEC, f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{raw}")
        time.sleep(0.15)
        if not r:
            continue
        plan = bool(re.search(r"<aff10b5One>\s*(1|true)\s*</aff10b5One>", r.text, re.I))
        for t in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", r.text, re.S):
            code = re.search(r"<transactionCode>\s*(\w)\s*</transactionCode>", t)
            sh = re.search(r"<transactionShares>\s*<value>\s*([\d.]+)", t)
            px = re.search(r"<transactionPricePerShare>\s*<value>\s*([\d.]+)", t)
            if not (code and sh and px):
                continue
            val = float(sh.group(1)) * float(px.group(1))
            if code.group(1) == "P":
                buys += val
            elif code.group(1) == "S":
                if plan:
                    planned += val
                else:
                    sells += val
    return n, buys, sells, planned


def eightk(sub):
    rec = (sub.get("filings") or {}).get("recent") or {}
    items = []
    for form, date, it in zip(rec.get("form", []), rec.get("filingDate", []), rec.get("items", [])):
        if form.startswith("8-K") and (TODAY - dt.date.fromisoformat(date)).days <= 30:
            items.append(f"{date}:{it}")
    return items


def short_interest(sym):
    r = get(NQ, f"https://api.nasdaq.com/api/quote/{sym}/short-interest", params={"assetClass": "stocks"})
    if not r:
        return None
    try:
        rows = ((r.json().get("data") or {}).get("shortInterestTable") or {}).get("rows") or []
        num = lambda s: float(str(s).replace(",", "")) if s not in (None, "", "N/A") else None
        pts = [(x.get("settlementDate"), num(x.get("interest")), num(x.get("daysToCover"))) for x in rows]
        pts = [p for p in pts if p[1]]
        if not pts:
            return None
        last = pts[0]
        prev = pts[2] if len(pts) > 2 else (pts[1] if len(pts) > 1 else None)
        ch = (last[1] / prev[1] - 1) * 100 if prev and prev[1] else None
        return last[0], last[1], last[2], ch
    except Exception:
        return None


def fmt(x, nd=1):
    return "" if x is None else f"{x:.{nd}f}"


def main() -> int:
    tickers = [t.strip().upper() for t in TICKERS.read_text().splitlines() if t.strip() and not t.startswith("#")]
    cmap = cik_map()
    rows = []
    for t in tickers:
        row = {"ticker": t}
        flags = []
        cik = cmap.get(t)
        row["cik"] = cik or ""
        if cik:
            fr = get(SEC, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
            time.sleep(0.15)
            facts = fr.json() if fr else {}
            rt, rq = quarters(facts, REV_TAGS)
            ot, oq = quarters(facts, OPI_TAGS)
            nt, nq = quarters(facts, NI_TAGS)
            row["last_quarter_end"] = max([x[-1][0] for x in (rq, oq, nq) if x] or [""])
            if t in os.getenv("EW_DEBUG", "").split(","):
                for name, ser in (("rev", rq), ("opi", oq), ("ni", nq)):
                    print("DEBUG", t, name, ser[-9:])
            row["rev_q_yoy_pct"] = fmt(yoy_last(rq))
            row["rev_ttm_yoy_pct"] = fmt(ttm_yoy(rq))
            row["opinc_q_yoy_pct"] = fmt(yoy_last(oq))
            row["opinc_ttm_yoy_pct"] = fmt(ttm_yoy(oq))
            row["ni_q_yoy_pct"] = fmt(yoy_last(nq))
            row["ni_ttm_yoy_pct"] = fmt(ttm_yoy(nq))
            row["tags"] = f"{rt or '-'}/{ot or '-'}/{nt or '-'}"
            prof_q = yoy_last(oq) if oq else yoy_last(nq)
            prof_t = ttm_yoy(oq) if oq else ttm_yoy(nq)
            if (prof_q is not None and prof_q < -20) or (prof_t is not None and prof_t < -10):
                flags.append("TRIM_DETERIORO")
            rv = ttm_yoy(rq)
            if rv is not None and rv < -3:
                flags.append("RICAVI_GIU")
            sr = get(SEC, f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            time.sleep(0.15)
            sub = sr.json() if sr else {}
            ek = eightk(sub)
            row["eightk_30d"] = " ; ".join(ek)
            allit = ",".join(ek)
            if any(i in allit for i in ("4.02", "1.03", "4.01")):
                flags.append("8K_ROSSO")
            elif any(i in allit for i in ("2.05", "2.06", "5.02")):
                flags.append("8K_ATTENZIONE")
            n4, b, s, pl = form4(cik, sub) if sub else (0, 0.0, 0.0, 0.0)
            row["form4_90d"] = n4
            row["insider_buys_90d_usd"] = f"{b:.0f}"
            row["insider_sales_90d_usd"] = f"{s:.0f}"
            row["insider_planned_sales_90d_usd"] = f"{pl:.0f}"
            if s > 5e6 and b == 0:
                flags.append("INSIDER_VENDITE")
            row["sec_status"] = "PRESENT" if facts else "MISSING"
        else:
            row["sec_status"] = "MISSING (CIK)"
        si = short_interest(t)
        if si:
            row["short_date"], row["short_interest"], row["days_to_cover"] = si[0], f"{si[1]:.0f}", fmt(si[2])
            row["short_change_pct"] = fmt(si[3])
            if si[3] is not None and si[3] >= 30:
                flags.append("SHORT_SU")
        else:
            row["short_date"] = row["short_interest"] = row["days_to_cover"] = row["short_change_pct"] = ""
        row["flags"] = " ".join(flags)
        row["level"] = "ROSSO" if "8K_ROSSO" in flags else ("GIALLO" if flags else "VERDE")
        rows.append(row)
        print(t, row["level"], row["flags"])
    fields = ["ticker", "level", "flags", "last_quarter_end", "rev_q_yoy_pct", "rev_ttm_yoy_pct",
              "opinc_q_yoy_pct", "opinc_ttm_yoy_pct", "ni_q_yoy_pct", "ni_ttm_yoy_pct", "eightk_30d",
              "form4_90d", "insider_buys_90d_usd", "insider_sales_90d_usd", "insider_planned_sales_90d_usd", "short_date", "short_interest",
              "days_to_cover", "short_change_pct", "tags", "sec_status", "cik"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "early_warning.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    (OUT / "early_warning_status.json").write_text(json.dumps({
        "version": "EARLY_WARNING v1.0",
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": ["SEC companyfacts", "SEC submissions (8-K items, Form 4)", "api.nasdaq.com short-interest"],
        "n": len(rows), "flagged": sum(1 for r in rows if r["flags"])}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
