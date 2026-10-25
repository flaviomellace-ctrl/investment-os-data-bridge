"""Primary-document provenance supplement; not an FSDS/S2 approval."""
import csv
import hashlib
import io
import json
from pathlib import Path

CANDIDATE_SHA = '9c51a0b017cd769425c128721e935819b0634942d050142b82c6bcae3bb2429d'
EVIDENCE_SHA = '2c38aa6d339df54562936e07d3ec66520c3f40afce38dac5ec544de32b0071f9'
SELECTED = ['short', 'long', 'collateral_financing', 'subordinated', 'cfe_notes']

def require(ok, message):
    if not ok:
        raise ValueError(message)

def audit(candidate, evidence):
    require(hashlib.sha256(candidate).hexdigest() == CANDIDATE_SHA, 'candidate hash')
    require(hashlib.sha256(evidence).hexdigest() == EVIDENCE_SHA, 'evidence hash')
    proof = json.loads(evidence)
    rows = {r['ticker']: r for r in csv.DictReader(io.StringIO(candidate.decode(), newline=''))}
    links = []

    def record(ticker, field, facts, accession, hashes, pointer):
        row = rows[ticker]
        require(row['annual_adsh'] == accession, 'filing mismatch')
        require(set(hashes) == {'xml', 'html'} and all(len(v)==64 for v in hashes.values()), 'source hashes')
        require(len({f['id'] for f in facts}) == len(facts), 'duplicate fact')
        for fact in facts:
            require(fact['instant'].replace('-', '') == row['annual_period'].split('.')[0], 'period mismatch')
            require(fact['unit'] == 'USD' and type(fact['value_usd']) is int and fact['value_usd'] >= 0, 'unit/value')
        require(sum(f['value_usd'] for f in facts) == int(row[field]), 'aggregate mismatch')
        components = ';'.join(f['concept'].split('}',1)[1]+'='+str(f['value_usd']) for f in facts)
        if field != 'cash_and_equivalents':
            require(row[field+'_components'] == components, 'component mismatch')
        else:
            require(row[field+'_tag'] == facts[0]['concept'].split('}',1)[1], 'cash tag')
            require(row[field+'_adsh'] == accession and row[field+'_uom'] == 'USD', 'cash provenance')
        links.append(dict(ticker=ticker,field=field,accession=accession,source_kind='ARCHIVED_PRIMARY_XBRL',source_hashes=hashes,evidence_pointer=pointer,facts=facts,value_usd=int(row[field]),supersedes_s1_used_as=field,fsds_face_membership_asserted=False))

    for i, company in enumerate(proof['debt_evidence']['companies']):
        t = company['ticker']; facts = company['facts']
        selected = SELECTED if t == 'MET' else ['short','long']
        coverage = set()
        for key in selected:
            f = facts[key]
            require(f['kind']=='liability' and f['coverage'] and not coverage.intersection(f['coverage']), 'overlapping or nonliability debt')
            coverage.update(f['coverage'])
        record(t,'long_term_debt',[facts['long']],company['accession'],company['source_sha256'],f'/debt_evidence/companies/{i}/facts/long')
        record(t,'total_debt',[facts[k] for k in selected],company['accession'],company['source_sha256'],f'/debt_evidence/companies/{i}/facts')
    for i, company in enumerate(proof['lease_evidence']):
        for j, observation in enumerate(company['lease_observations']):
            f = observation['direct_fact']; tag = f['concept'].split('}',1)[1]
            require(tag in ['FinanceLeaseLiability','OperatingLeaseLiability'], 'lease concept')
            if 'undiscounted' in observation:
                require(observation['undiscounted']['value_usd']-observation['interest']['value_usd']==f['value_usd'], 'lease present value')
            field = ('finance' if tag=='FinanceLeaseLiability' else 'operating')+'_lease_liabilities'
            record(company['ticker'],field,[f],company['accession'],company['source_hashes'],f'/lease_evidence/{i}/lease_observations/{j}/direct_fact')
    cash = proof['cash_evidence']
    record('CVX','cash_and_equivalents',[cash['facts']['cash']],cash['accession'],cash['source_hashes'],'/cash_evidence/facts/cash')
    require(len(links)==20 and len({(x['ticker'],x['field']) for x in links})==20, 'coverage')
    return dict(schema='br04_data09_primary_component_links_v1',candidate_sha256=CANDIDATE_SHA,primary_evidence_sha256=EVIDENCE_SHA,aggregate_links=len(links),fact_links=sum(len(x['facts']) for x in links),links=links,all_aggregates_reconciled=True,source_authentication='ARCHIVED_COPY_HASHES_ONLY_NOT_NEW_SEC_AUTHENTICATION',full_s2_passed=False,full_s3_passed=False,full_s4_passed=False,candidate_promoted=False,buy_add_allowed=False)

if __name__ == '__main__':
    root=Path(__file__).resolve().parents[1]/'data/research/br04-data09'
    result=audit((root/'RESEARCH_NOT_PROMOTED.csv').read_bytes(),(root/'primary_evidence.json').read_bytes())
    (root/'primary_component_links.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='links'},indent=2))
