"""Diagnostic only: list XBRL tags each filing used for revenue, operating cash flow and share counts (SEC companyfacts)."""
import json, os, re, time, requests
cfg = json.load(open("pit/probe_tags.json"))
H = {"User-Agent": f"InvestmentOS research {os.environ.get('SEC_CONTACT_EMAIL','research@example.com')}"}
pat = re.compile(r"Revenue|Sales|OperatingActivities|SharesOutstanding|NumberOfShare|NumberOfDiluted", re.I)
out = []
for p in cfg["pairs"]:
    cik = str(int(float(p["cik"]))).zfill(10) if p["cik"] else ""
    if not cik or not p["adsh"]:
        out.append(f"{p['ticker']} {p['which']}: no cik/adsh"); continue
    time.sleep(0.4)
    r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=H, timeout=60)
    if r.status_code != 200:
        out.append(f"{p['ticker']}: HTTP {r.status_code}"); continue
    facts = r.json().get("facts", {})
    found = []
    for ns, tags in facts.items():
        for tag, obj in tags.items():
            if not pat.search(tag): continue
            for unit, vals in obj.get("units", {}).items():
                for v in vals:
                    if v.get("accn") == p["adsh"] and v.get("fp") == "FY" and v.get("form") in ("10-K", "10-K/A", "20-F"):
                        dur = ""
                        if v.get("start"):
                            from datetime import date
                            dur = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
                        found.append(f"{ns}:{tag} [{unit}] end={v.get('end')} days={dur} val={v.get('val')}")
    out.append(f"== {p['ticker']} {p['which']} {p['adsh']}\n" + "\n".join(sorted(set(found))[:40]))
os.makedirs("pit/out", exist_ok=True)
open("pit/out/probe_tags.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out)[:20000])
