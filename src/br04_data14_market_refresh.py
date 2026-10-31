"""Explicit market-only rebase of DATA12; fresh custody and compatibility checks."""
import csv,io,json,hashlib,math
from collections import Counter
from pathlib import Path
try:
    from .br04_historical_base import BASE_SHA
except ImportError:
    from br04_historical_base import BASE_SHA
ROOT=Path(__file__).resolve().parents[1]
CURRENT_SHA='91b0f052957e6a0a34768cfb48838bafe9d2f7f589c3ad439f95c7178e6125e2'
INPUT_SHA='6c444950cc89d955231a3fd8dc34cd6f34921734ab3e124ccc81aefd74d7bca9'
MARKET_FIELDS={'market_price','market_cap','market_data_retrieved_at_utc'}
def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(data):
    reader=csv.DictReader(io.StringIO(data.decode(),newline=''));return reader.fieldnames,list(reader)
def rebase(old,current,candidate):
    for raw,pin,name in [(old,BASE_SHA,'historical base'),(current,CURRENT_SHA,'current base'),(candidate,INPUT_SHA,'DATA12')]:require(sha(raw)==pin,name+' hash mismatch')
    h,a=read(old);hc,b=read(current);hd,c=read(candidate)
    require(h==hc and hd[:212]==h and len(h)==212 and len(hd)==285,'column mismatch')
    require(len(a)==len(b)==len(c)==504 and len({r['ticker'] for r in a})==504,'universe mismatch')
    changes=[];result=[];retained=0
    for prior,new,amended in zip(a,b,c):
        require(prior['ticker']==new['ticker']==amended['ticker'],'row identity mismatch')
        for key in h:
            if prior[key]!=new[key]:
                require(key in MARKET_FIELDS,'non-market base change')
                changes.append({'ticker':prior['ticker'],'field':key,'before':prior[key],'after':new[key]})
            if key not in MARKET_FIELDS and amended[key]!=prior[key]:retained+=1
        row=dict(amended)
        for key in MARKET_FIELDS:row[key]=new[key]
        require(all(row[k]==amended[k] for k in hd if k not in MARKET_FIELDS),'fundamental amendment lost')
        result.append(row)
    counts=Counter(x['field'] for x in changes)
    require(dict(counts)=={k:502 for k in MARKET_FIELDS},'refresh scope changed')
    output=io.StringIO(newline='');w=csv.DictWriter(output,fieldnames=hd);w.writeheader();w.writerows(result);out=output.getvalue().encode()
    report={'schema':'br04_data14_market_rebase_v1','historical_base_sha256':BASE_SHA,'current_base_sha256':CURRENT_SHA,'input_candidate_sha256':INPUT_SHA,'candidate_sha256':sha(out),'rows':504,'columns':285,'changed_cells':len(changes),'changed_rows':len({x['ticker'] for x in changes}),'changed_field_counts':dict(sorted(counts.items())),'legacy_amended_cells_preserved':retained,'all_non_market_candidate_fields_preserved':True,'all_br04_fields_preserved':True,'historical_approvals_transferred':False,'candidate_promoted':False,'economic_clearance':False,'buy_add_allowed':False}
    return out,report,changes

def verify_transport(data,directory,index):
    # Independent raw-record parser from the frozen preflight, not the splitter.
    from br04_data09_preflight import csv_records_raw
    records=csv_records_raw(data);parts=index['parts'];assembled=[records[0]];next_row=1
    require(index['source_sha256']==sha(data),'index source mismatch')
    for part in parts:
        name=part['filename'];require(Path(name).name==name,'unsafe part path')
        body=(directory/name).read_bytes();rows=csv_records_raw(body)
        require(sha(body)==part['sha256'] and len(body)==part['bytes'] and len(body)<=58000,'chunk hash/size mismatch')
        require(rows[0]==records[0] and len(rows)-1==part['rows'],'chunk header/count mismatch')
        require(part['row_start_1_based']==next_row and part['row_end_1_based']==next_row+len(rows)-2,'chunk range mismatch')
        next_row+=len(rows)-1;assembled.extend(rows[1:])
    require(next_row==505 and b''.join(assembled)==data,'reassembly differs')
    return {'parts':len(parts),'rows':504,'reassembled_byte_identical':True,'candidate_sha256':sha(data)}

def main():
    from br04_historical_base import restore
    from br04_data09_runtime import restore_runtime
    from br04_data09_preflight import load_frozen_engine,derive
    from split_for_claude import split_file
    current=ROOT/'data/current/sp500_fundamentals.csv';before=current.read_bytes()
    source=ROOT/'data/research/br04-data12/RESEARCH_NOT_PROMOTED.csv'
    data,report,changes=rebase(restore(ROOT).read_bytes(),before,source.read_bytes())
    # A fresh archived fundamental replay is a prerequisite, not approval of DATA14.
    previous=json.loads((ROOT/'data/research/br04-data09/research_regression.json').read_bytes())
    require(previous['overall_passed'] is True and previous['phase']=='S2_RESEARCH' and previous['base_scope']=='HISTORICAL_REPLAY' and previous['base_canonical_sha256']==BASE_SHA and previous['candidate_sha256']=='9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d','fresh archived regression missing')
    require(not previous['failed_tests'] and not previous['failed_gates'] and previous['candidate_promoted'] is False and previous['buy_add_allowed'] is False,'archived regression gate failed')
    out=ROOT/'data/research/br04-data14';out.mkdir(parents=True,exist_ok=True);target=out/'RESEARCH_NOT_PROMOTED.csv';target.write_bytes(data)
    index=split_file(source=target,output_dir=out,url_base=None)
    transport=verify_transport(data,out,index)
    restore_runtime(ROOT);engine,md5=load_frozen_engine();confidence=Counter();processed=0;ios_count=0
    for row in read(data)[1]:
        c=derive(row,engine);score,cov,detail,_=engine.bqs(c)
        confidence[engine.bqs_confidence(cov,c.get('data_coverage_pct') or 0,'PRESENT',detail.get('_metric_coverage_pct',0),detail.get('_provisional_components',[]))]+=1
        if score is not None and score>=engine.IOS_GATE['min_bqs'] and (c.get('data_coverage_pct') or 0)>=engine.IOS_GATE['min_data_coverage']:
            value,_=engine.ios(c,score,cov);ios_count+=value is not None
        processed+=1
    require(processed==504 and current.read_bytes()==before and target.read_bytes()==data,'runtime mutation/count failure')
    report.update(overall_passed=True,validation_scope='MARKET_ONLY_REBASE_AND_TRANSPORT_ENGINE_COMPATIBILITY_NOT_RELEASE_APPROVAL',archived_regression_report_sha256=sha((ROOT/'data/research/br04-data09/research_regression.json').read_bytes()),transport=transport,engine={'md5':md5,'rows_processed':processed,'exceptions':0,'confidence_counts':dict(confidence),'ios_computable_rows':ios_count},canonical_unchanged=True)
    for name,value in [('rebase.json',report),('market_changes.json',changes)]: (out/name).write_text(json.dumps(value,indent=2)+'\n')
    print('DATA14_REPORT='+json.dumps(report,separators=(',',':')))
if __name__=='__main__':main()
