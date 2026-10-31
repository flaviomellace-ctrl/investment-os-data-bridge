"""Explicit DATA09 research inputs; never creates a promotion-eligible S1 run."""
import csv
import io
import json
from pathlib import Path
import audit_br04_data09 as primary
import rebase_br04_data09 as rebase

SOURCE_RUN = '40122845921'

def read_rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def component_identity(row):
    return tuple(row.get(k,'') for k in ['ticker','adsh','used_as','tag','value','ddate','qtrs','uom','source_kind','primary_fact_id','stmt','fsds_version','line'])

def prepare(root):
    source=root/'data/staging/br04'/SOURCE_RUN
    research=root/'data/research/br04-data09'
    data, receipt=rebase.reconstruct((source/'candidate/sp500_fundamentals.csv').read_bytes(),(research/'manifest.json').read_bytes())
    evidence=(research/'primary_evidence.json').read_bytes()
    audit=primary.audit(data,evidence)
    proof=json.loads(evidence)
    original=read_rows(source/'evidence/br04_components.csv')
    replacements={(link['ticker'],link['field']) for link in audit['links']}
    retained=[dict(r) for r in original if (r['ticker'],r['used_as']) not in replacements]
    superseded=[dict(r) for r in original if (r['ticker'],r['used_as']) in replacements]
    added=[]
    for link in audit['links']:
        for fact in link['facts']:
            namespace,tag=fact['concept'][1:].split('}',1)
            added.append(dict(ticker=link['ticker'],adsh=link['accession'],used_as=link['field'],stmt='BS',line='',plabel=fact.get('caption',''),tag=tag,version=namespace,value=str(fact['value_usd']),ddate=fact['instant'].replace('-',''),qtrs='0',uom=fact['unit'],source_kind='ARCHIVED_PRIMARY_XBRL',primary_fact_id=fact['id'],fsds_version=(namespace.replace('http://fasb.org/','') if namespace.startswith('http://fasb.org/us-gaap/') else link['accession'])))
    custom=read_rows(source/'audit/br04_custom_lines_audit.csv')
    jpm=next(c for c in proof['debt_evidence']['companies'] if c['ticker']=='JPM')
    asset=jpm['facts']['loans_asset']
    primary.require(asset['kind']=='asset','loan asset evidence')
    reclassified=[]
    for row in custom:
        if row['ticker']=='JPM' and row['tag']==asset['concept'].split('}',1)[1]:
            primary.require(row['adsh']==jpm['accession'] and int(row['value'])==asset['value_usd'] and row['assigned_class']=='CUSTOM_DEBT','loan asset audit identity')
            reclassified.append(dict(row))
            row['assigned_class']='CUSTOM_NON_DEBT'
    primary.require(len(reclassified)==1,'exact loan asset reclassification')
    report=json.loads((source/'evidence/br04_s1_build.json').read_text())
    primary.require(report['candidate_sha256']==rebase.INPUT_SHA,'original S1 custody')
    report=dict(report,candidate_sha256=primary.CANDIDATE_SHA)
    research.mkdir(parents=True,exist_ok=True)
    candidate=research/'RESEARCH_NOT_PROMOTED.csv';candidate.write_bytes(data)
    status=research/'status_research.md'
    status.write_text('Research only; leverage indeterminate: 212.\n`MISSING` resta `MISSING`: nessuna assenza è convertita in zero\nNo promotion or BUY/ADD.\n')
    provenance=dict(source_s1_run=SOURCE_RUN,source_s1_sha256=rebase.INPUT_SHA,candidate_sha256=primary.CANDIDATE_SHA,retained_fsds_components=len(retained),superseded_fsds_components=superseded,primary_components_added=added,custom_reclassifications=reclassified,primary_evidence_sha256=primary.EVIDENCE_SHA,contract='Research extension: T11 uses pinned primary facts; T24 still requires independent PRE face membership for every total-debt component.',original_fsds_contract_approval=False,candidate_promoted=False)
    (research/'regression_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return dict(source=source,research=research,candidate=candidate,status=status,metadata=report,components=retained+added,custom=custom,primary_keys={component_identity(r) for r in added},audit=audit,retained_fsds_components=len(retained),superseded_fsds_components=len(superseded))
