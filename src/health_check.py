#!/usr/bin/env python3
"""Controllo di salute dei dati automatici. Esce con codice 1 e scrive health_report.md se qualcosa è vecchio o mancante."""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "data" / "current"
NOW = dt.datetime.now(dt.timezone.utc)
problems, ok = [], []


def age_days(ts):
    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (NOW - t).total_seconds() / 86400


def check(name, fn, max_days):
    try:
        ts, detail = fn()
        a = age_days(ts)
        (problems if a > max_days else ok).append(f"{name}: aggiornato {ts} ({a:.1f} giorni fa) {detail}".strip())
    except Exception as exc:
        problems.append(f"{name}: illeggibile o assente ({type(exc).__name__})")


def prices():
    rows = list(csv.DictReader(open(CUR / "watchlist_prices.csv")))
    miss = [r["ticker"] for r in rows if r["status"] != "PRESENT"]
    return rows[0]["fetched_at_utc"], f"mancanti: {','.join(miss)}" if miss else ""


def margine():
    d = json.load(open(CUR / "margine_status.json"))
    return d["fetched_at_utc"], f"{d['present']}/{d['total']} simboli"


def warning():
    d = json.load(open(CUR / "early_warning_status.json"))
    return d["fetched_at_utc"], f"{d['n']} titoli, {d['flagged']} con campanelli"


def estimates():
    files = sorted((ROOT / "data" / "estimates").glob("*.csv"))
    rows = list(csv.DictReader(open(files[-1])))
    present = sum(1 for r in rows if r["status"] == "PRESENT")
    return files[-1].stem + "T23:00:00Z", f"{present}/{len(rows)} con stime"


def fundamentals():
    m = json.load(open(CUR / "manifest.json"))
    ts = m.get("generated_at_utc") or m.get("generated_at") or m.get("updated_at_utc")
    return ts, ""


weekend = NOW.weekday() >= 5
slack = 2 if not weekend else 3
check("Prezzi lista d'attesa", prices, slack + 0.5)
check("Dati Il Margine", margine, slack + 0.5)
check("Campanelli EARLY WARNING", warning, slack + 0.5)
check("Archivio stime", estimates, slack + 1)
check("Fondamentali S&P 500 (settimanale)", fundamentals, 8)

report = ["# Salute dei dati automatici", f"Controllo: {NOW.strftime('%Y-%m-%d %H:%M UTC')}", ""]
report += ["## Problemi"] + [f"- {p}" for p in problems] if problems else ["Nessun problema."]
report += ["", "## In regola"] + [f"- {o}" for o in ok]
(ROOT / "health_report.md").write_text("\n".join(report) + "\n")
print("\n".join(report))
sys.exit(1 if problems else 0)
