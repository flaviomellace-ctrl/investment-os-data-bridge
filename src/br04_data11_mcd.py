"""Five-cell MCD legacy amendment; research only, no inherited S2 approval."""
import csv, hashlib, io, json, math
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
INPUT_SHA='9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d'
PROOF_SHA='0a143694130f1a2a9d6592a42350023ecf205b9e4d3aafe19d9ab61771b1b676'
RECEIPT_SHA='668849c6473189cbdfde48b0818cd301a10a5d1272a2979e9241320e860ecc86'
FIELDS=['annual_diluted_shares','prior_diluted_shares','fy_minus_1_diluted_shares','fy_minus_2_diluted_shares','fy_minus_3_diluted_shares']
def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def amend(data,proof_bytes):
    require(sha(data)==INPUT_SHA,'input hash mismatch')
    require(sha(proof_bytes)==PROOF_SHA,'proof hash mismatch')
    reader=csv.DictReader(io.StringIO(data.decode())); header=reader.fieldnames; rows=list(reader)
    require(len(rows)==504 and len(header)==285,'shape mismatch')
    original=[dict(r) for r in rows]; row=next(r for r in rows if r['ticker']=='MCD')
    proofs=json.loads(proof_bytes)
    for field,ev in zip(FIELDS,proofs[:5]):
        require(ev['field']==field and ev['ticker']=='MCD' and ev['multiplier']==1000000,'proof identity mismatch')
        require(sha(ev['table_text'].encode())==ev['table_text_sha256'],'table hash mismatch')
        require('In millions, except per share data' in ev['table_text'] and 'Weighted-average shares outstanding' in ev['table_text'],'unit authority missing')
        row[field]=repr(float(Decimal(ev['fact']['value'])*1000000))
    def fcf(pre): return float(row[pre+'operating_cash_flow'])-float(row[pre+'capex'])
    now=fcf('annual_')/float(row['annual_diluted_shares']); old=fcf('fy_minus_3_')/float(row['fy_minus_3_diluted_shares'])
    require(all(math.isfinite(v) and v>0 for v in [now,old]),'invalid CAGR inputs')
    row['fcf_per_share_cagr3']=repr((now/old)**(1/3)-1)
    ledger=[{'ticker':a['ticker'],'field':k,'before':a[k],'after':b[k]} for a,b in zip(original,rows) for k in header if a[k]!=b[k]]
    require({(x['ticker'],x['field']) for x in ledger}=={('MCD',k) for k in FIELDS[:4]+['fcf_per_share_cagr3']},'unexpected change scope')
    output=io.StringIO(newline='');w=csv.DictWriter(output,fieldnames=header);w.writeheader();w.writerows(rows)
    result=output.getvalue().encode()
    report={'schema':'br04_data11_mcd_amendment_v1','input_sha256':sha(data),'candidate_sha256':sha(result),'proof_sha256':PROOF_SHA,'changed_cells':ledger,'unchanged_other_rows':503,'br04_fields_preserved':True,'original_fsds_contract_approval':False,'data09_s2_approval_inherited':False,'candidate_promoted':False,'economic_clearance':False,'buy_add_allowed':False}
    return result,report

def verify_archive(directory,proof_bytes):
    from br04_primary_filing import Sources
    require(sha(proof_bytes)==PROOF_SHA,'proof hash mismatch')
    sources=Sources(directory,RECEIPT_SHA,38277084865,'b99ecc7a8a9d430b151f7da69919ef67b79d81fb')
    verified=[]
    for ev in json.loads(proof_bytes)[:5]:
        f=ev['fact']; fact=sources.one(f['accession'],63908,f['concept'],f['end'],f['start'])
        fresh=sources.table(fact,ev['caption_required'])
        require(fresh['fact']==f and fresh['table_text_sha256']==ev['table_text_sha256'] and fresh['inline_scale']==ev['inline_scale'],'archived primary proof mismatch')
        verified.append({'field':ev['field'],'accession':f['accession'],'table_text_sha256':fresh['table_text_sha256']})
    return {'schema':'br04_data11_archive_verification_v1','receipt_sha256':RECEIPT_SHA,'proof_sha256':PROOF_SHA,'verified_facts':verified,'all_receipt_files_hash_verified':True,'fresh_sec_fetch':False,'economic_clearance':False,'buy_add_allowed':False}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--archive');args=p.parse_args()
    proof=(ROOT/'data/research/br04-data10/prior_rc1_proofs.json').read_bytes()
    data=(ROOT/'data/research/br04-data09/RESEARCH_NOT_PROMOTED.csv').read_bytes()
    out,report=amend(data,proof); dest=ROOT/'data/research/br04-data11';dest.mkdir(exist_ok=True,parents=True)
    if args.archive:
        (dest/'archive_verification.json').write_text(json.dumps(verify_archive(args.archive,proof),indent=2)+'\n')
    (dest/'RESEARCH_NOT_PROMOTED.csv').write_bytes(out)
    (dest/'amendment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
