"""Reconstruct the immutable pre-refresh canonical fixture from pinned S1."""
import csv,hashlib,io
from pathlib import Path
S1_SHA='e108b517924ceced165d356874b5e0a4598ec9a103d452f034ff4431ab34f9e0'
BASE_SHA='51249aad299ba874b4e688993aa1a4491cc5556cf6c3f0ede339504d672e0dcf'
def reconstruct(data):
    if hashlib.sha256(data).hexdigest()!=S1_SHA:raise ValueError('historical S1 hash mismatch')
    rows=list(csv.reader(io.StringIO(data.decode(),newline='')))
    s=io.StringIO(newline='');csv.writer(s,lineterminator='\n').writerows([r[:212] for r in rows]);out=s.getvalue().encode()
    if hashlib.sha256(out).hexdigest()!=BASE_SHA:raise ValueError('historical canonical hash mismatch')
    return out

def restore(root):
    data=reconstruct((root/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes())
    p=root/'data/research/br04-data09/historical_canonical.csv';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
if __name__=='__main__':print(restore(Path(__file__).resolve().parents[1]))
