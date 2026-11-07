"""Aggregate-only frozen engine compatibility; not S2/S3/S4 approval."""
import csv,io,json
from collections import Counter
from br04_data11_mcd import ROOT,amend,sha,require
from br04_data09_preflight import load_frozen_engine,derive

def main():
    folder=ROOT/'data/research/br04-data11'
    data,amendment=amend((ROOT/'data/research/br04-data09/RESEARCH_NOT_PROMOTED.csv').read_bytes(),(ROOT/'data/research/br04-data10/prior_rc1_proofs.json').read_bytes())
    require((folder/'RESEARCH_NOT_PROMOTED.csv').read_bytes()==data,'candidate differs')
    engine,md5=load_frozen_engine();confidence=Counter();count=0;ios_count=0
    for row in csv.DictReader(io.StringIO(data.decode())):
        c=derive(row,engine);score,cov,detail,flags=engine.bqs(c)
        confidence[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            result,_=engine.ios(c,score,cov);ios_count+=result is not None
        count+=1
    require(count==504,'row count differs')
    report={'schema':'br04_data11_engine_compatibility_v1','candidate_sha256':sha(data),'engine_md5':md5,'rows_processed':count,'exceptions':0,'confidence_counts':dict(confidence),'ios_computable_rows':ios_count,'original_fsds_contract_approval':False,'s2_s3_s4_approval_inherited':False,'candidate_promoted':False,'economic_clearance':False,'buy_add_allowed':False}
    (folder/'engine_compatibility.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
