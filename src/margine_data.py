#!/usr/bin/env python3
"""
Il Margine - dati di mercato senza il PC di Flavio.

Porta in Python le funzioni __g2 / __g3 del playbook (claude/IL_MARGINE_PLAYBOOK.md)
e il calcolo del rischio per orizzonte del playbook radar. Fonte: Yahoo Finance chart API.

Scrive in data/current/:
- margine_DATA.txt  righe "simbolo|nome|valuta|prezzo|var.giorno%|r1m|r6m|rytd|r1a|r3a|r5a|t0|t1|40 punti base 100"
- margine_RET.txt   righe "simbolo|5G|1M|6M|YTD|1A|3A|5A|data"
- margine_RISK.csv  per i titoli del radar: volte in perdita / 5% peggiore / caso tipico / 5% migliore
                    a 5, 21, 126, 252 sedute; calo massimo a 5 anni
- margine_status.json  esito per simbolo, ora di aggiornamento

Un simbolo che fallisce resta MISSING: nessun numero inventato.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "current"
SYMS = ROOT / "data" / "margine_symbols.txt"
RADAR = ROOT / "data" / "watchlist_tickers.txt"
HOSTS = ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept": "application/json,text/plain,*/*"}
S = requests.Session()
S.headers.update(HDR)


def chart(sym: str, rng: str, interval: str):
    err = ""
    for attempt in range(4):
        host = HOSTS[attempt % 2]
        try:
            r = S.get(f"{host}/v8/finance/chart/{requests.utils.quote(sym)}",
                      params={"range": rng, "interval": interval}, timeout=30)
            if r.status_code == 200:
                res = (r.json().get("chart") or {}).get("result") or []
                if res:
                    return res[0], ""
                err = "risultato vuoto"
            else:
                err = f"HTTP {r.status_code}"
        except Exception as exc:
            err = type(exc).__name__
        time.sleep(2 + 3 * attempt)
    return None, err


def series(R):
    ts = R.get("timestamp") or []
    ind = R.get("indicators") or {}
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
    q = adj or (ind.get("quote") or [{}])[0].get("close") or []
    return [(t, v) for t, v in zip(ts, q) if v is not None]


def pct(a, b):
    return f"{(a / b - 1) * 100:.1f}"


def at_or_before(P, t):
    b = None
    for p in P:
        if p[0] <= t:
            b = p
        else:
            break
    return b


def month_back(d: dt.datetime, m: int) -> float:
    y, mo = d.year, d.month - m
    while mo <= 0:
        mo += 12
        y -= 1
    day = min(d.day, calendar.monthrange(y, mo)[1])
    return dt.datetime(y, mo, day, d.hour, d.minute, tzinfo=dt.timezone.utc).timestamp() + 43200


def g2(sym, R):
    m = R.get("meta") or {}
    P = series(R)
    last, now = P[-1], P[-1][0]
    back = lambda d: (pct(last[1], b[1]) if (b := at_or_before(P, now - d * 86400)) else "")
    y0 = dt.datetime(dt.datetime.utcfromtimestamp(now).year, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    yb = None
    for p in P:
        if p[0] < y0:
            yb = p
    n = 40
    Sx = [P[round(k * (len(P) - 1) / (n - 1))] for k in range(n)]
    base = Sx[0][1]
    name = (m.get("longName") or m.get("shortName") or sym).replace("|", " ").replace("~", " ")
    chg = m.get("regularMarketChangePercent")
    return "|".join(str(x) for x in [
        sym, name, m.get("currency", ""), m.get("regularMarketPrice", ""),
        f"{chg:.2f}" if isinstance(chg, (int, float)) else "",
        back(30), back(182), pct(last[1], yb[1]) if yb else "", back(365), back(1095),
        pct(last[1], P[0][1]) if P[0][0] <= now - 1800 * 86400 else "",
        Sx[0][0], m.get("regularMarketTime", ""),
        ",".join(str(round(p[1] / base * 100)) for p in Sx)])


def g3(sym, R):
    P = series(R)
    last, now = P[-1], P[-1][0]
    D = dt.datetime.fromtimestamp(now, dt.timezone.utc)
    at = lambda t: (pct(last[1], b[1]) if (b := at_or_before(P, t)) else "")
    y0 = dt.datetime(D.year, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    line = "|".join([
        sym, pct(last[1], P[-6][1]) if len(P) > 5 else "",
        at(month_back(D, 1)), at(month_back(D, 6)), at(y0), at(month_back(D, 12)), at(month_back(D, 36)),
        pct(last[1], P[0][1]) if P[0][0] <= now - 1800 * 86400 else "", D.date().isoformat()])
    day_chg = f"{(P[-1][1] / P[-2][1] - 1) * 100:.2f}" if len(P) > 1 else ""
    return line, day_chg, P


def risk(P):
    px = [v for _, v in P]
    out = {}
    for n in (5, 21, 126, 252):
        r = sorted((px[i] / px[i - n] - 1) * 100 for i in range(n, len(px)))
        if not r:
            continue
        q = lambda f: f"{r[int(f * (len(r) - 1))]:.1f}"
        out[n] = (f"{sum(1 for x in r if x < 0) / len(r) * 100:.0f}", q(0.05), q(0.5), q(0.95))
    peak, mdd = px[0], 0.0
    for v in px:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return out, f"{mdd * 100:.0f}"


def main() -> int:
    syms = [s.strip() for s in SYMS.read_text().splitlines() if s.strip() and not s.startswith("#")]
    radar = [s.strip().upper() for s in RADAR.read_text().splitlines() if s.strip() and not s.startswith("#")]
    data, ret, status, risk_rows = [], [], {}, []
    for s in syms + [r for r in radar if r not in syms]:
        Rd, e1 = chart(s, "5y", "1d")
        if not Rd or len(series(Rd)) < 10:
            status[s] = f"MISSING ({e1 or 'serie corta'})"
            print(s, status[s])
            continue
        rline, day_chg, Pd = g3(s, Rd)
        if s in syms:
            Rw, e2 = chart(s, "5y", "1wk")
            if Rw and len(series(Rw)) >= 40:
                d = g2(s, Rw).split("|")
                if d[4] == "":
                    d[4] = day_chg
                data.append("|".join(d))
                ret.append(rline)
                status[s] = "PRESENT"
            else:
                status[s] = f"MISSING settimanale ({e2})"
        if s in radar:
            rk, mdd = risk(Pd)
            row = {"ticker": s, "date": rline.split("|")[-1], "max_drawdown_5y_pct": mdd}
            for n, lab in ((5, "1w"), (21, "1m"), (126, "6m"), (252, "1y")):
                v = rk.get(n, ("", "", "", ""))
                row.update({f"{lab}_loss_share_pct": v[0], f"{lab}_p05": v[1],
                            f"{lab}_p50": v[2], f"{lab}_p95": v[3]})
            risk_rows.append(row)
            status.setdefault(s, "PRESENT")
        print(s, status.get(s))
        time.sleep(0.4)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "margine_DATA.txt").write_text("\n".join(data) + "\n")
    (OUT / "margine_RET.txt").write_text("\n".join(ret) + "\n")
    if risk_rows:
        import csv
        with open(OUT / "margine_RISK.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(risk_rows[0].keys()))
            w.writeheader()
            w.writerows(risk_rows)
    (OUT / "margine_status.json").write_text(json.dumps({
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Yahoo Finance chart API (adjclose dove disponibile)",
        "present": sum(1 for v in status.values() if v == "PRESENT"),
        "total": len(status), "status": status}, indent=1, ensure_ascii=False))
    bench = []
    for b in ("IMIE.MI", "SPYI.DE"):
        Rb, eb = chart(b, "1mo", "1d")
        Pb = series(Rb) if Rb else []
        if Pb:
            d = dt.datetime.fromtimestamp(Pb[-1][0], dt.timezone.utc).date().isoformat()
            bench.append(f"{b},{d},{Pb[-1][1]:.4f},{(Rb.get('meta') or {}).get('currency','')},PRESENT")
        else:
            bench.append(f"{b},,,,MISSING ({eb})")
    (OUT / "benchmark_prices.csv").write_text("symbol,date,close_adj,currency,status\n" + "\n".join(bench) + "\n")
    ok = sum(1 for v in status.values() if v == "PRESENT")
    print(f"PRESENT {ok}/{len(status)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
