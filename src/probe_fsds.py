"""Diagnostic only: raw FSDS num.txt rows for selected filings and tag prefixes."""
import io, os, sys, zipfile, requests, pandas as pd
H = {"User-Agent": f"InvestmentOS research {os.environ.get('SEC_CONTACT_EMAIL','research@example.com')}"}
q = "2021q1"
targets = {"0001579241-21-000020": "ALLE", "0000021665-21-000007": "CL", "0000093410-21-000009": "CVX", "0001652044-21-000010": "GOOGL"}
r = requests.get(f"https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip", headers=H, timeout=600)
r.raise_for_status()
zf = zipfile.ZipFile(io.BytesIO(r.content))
sub = pd.read_csv(zf.open("sub.txt"), sep="\t", dtype=str)
out = []
for name in ("ALLE", "CL", "CVX", "GOOGL"):
    pass
cik_rows = sub[sub["name"].str.contains("ALLEGION|COLGATE|CHEVRON CORP|ALPHABET", case=False, na=False) & sub["form"].eq("10-K")]
out.append(cik_rows[["adsh", "name", "form", "period", "filed"]].to_string())
adsh = set(cik_rows["adsh"])
for chunk in pd.read_csv(zf.open("num.txt"), sep="\t", dtype=str, chunksize=500000):
    m = chunk["adsh"].isin(adsh) & chunk["tag"].str.startswith(("WeightedAverageNumber", "RevenueFromContract", "Revenues"))
    if m.any():
        out.append(chunk.loc[m].to_string(max_colwidth=60))
os.makedirs("pit/out", exist_ok=True)
open("pit/out/probe_fsds.txt", "w").write("\n".join(out))
print("\n".join(out)[:30000])
