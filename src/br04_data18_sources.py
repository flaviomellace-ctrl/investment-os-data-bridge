"""Reproduce historical-share proofs from the pinned archive and S1 CSV."""
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path
from lxml import etree,html
from decimal import Decimal
RECEIPT='668849c6473189cbdfde48b0818cd301a10a5d1272a2979e9241320e860ecc86'
S1='e108b517924ceced165d356874b5e0a4598ec9a103d452f034ff4431ab34f9e0'
TAG='WeightedAverageNumberOfDilutedSharesOutstanding'
def sha(b):return hashlib.sha256(b).hexdigest()
def build(archive,s1):
    assert sha(s1)==S1
    rows={r['ticker']:r for r in csv.DictReader(io.StringIO(s1.decode()))}
    z=zipfile.ZipFile(archive);prefix='v43-semidefinitive-rc1_6/evidence/remaining-primary-38277084865/'
    receipt=z.read(prefix+'PRIMARY_RECEIPT.json');assert sha(receipt)==RECEIPT
    entries={e['file']:e for e in json.loads(receipt)['entries']}
    def read(p):
        b=z.read(prefix+p);e=entries[p];assert sha(b)==e['sha256'] and len(b)==e['bytes'];return b
    observations=[]
    for ticker,cik in [('IP',51434),('MET',1099219),('CVX',93410)]:
        row=rows[ticker];p=f'raw/CIK{cik:010d}_companyfacts.json';b=read(p);cf=json.loads(b);assert cf['cik']==cik
        fs=cf['facts']['us-gaap'][TAG]['units']['shares']
        acc=row['annual_adsh'];instance=read('raw/'+acc+'_instance.xml');primary=read('raw/'+acc+'_primary.htm')
        root=etree.fromstring(instance,etree.XMLParser(resolve_entities=False,no_network=True));doc=html.fromstring(primary)
        for i in (1,2,3):
            year=2025-i;pre=f'fy_minus_{i}_';start=f'{year}-01-01';end=f'{year}-12-31';target=row[pre+'adsh']
            exact=[f for f in fs if f.get('accn')==target and f.get('start')==start and f.get('end')==end]
            assert len(exact)==1;f=exact[0]
            assert f['form']=='10-K' and f['fp']=='FY' and f['fy']==year and f['val']>0
            assert f['filed'].replace('-','')==str(int(float(row[pre+'filed'])))
            assert end.replace('-','')==str(int(float(row[pre+'period'])))
            supporting=[x for x in fs if x.get('start')==start and x.get('end')==end and x.get('form')=='10-K' and x.get('filed','')<='2026-10-12']
            assert len({x['accn'] for x in supporting})>=2 and {x['val'] for x in supporting}=={f['val']}
            ev=dict(ticker=ticker,field=pre+'diluted_shares',concept=TAG,unit='shares',fact=f,companyfacts_sha256=sha(b),companyfacts_url=entries[p]['url'],corroborating_facts=supporting)
            if i<3:
                matches=[]
                for node in root:
                    if etree.QName(node).localname!=TAG:continue
                    cs=root.xpath('//*[local-name()="context" and @id=$id]',id=node.get('contextRef'))
                    if len(cs)!=1:continue
                    c=cs[0]
                    if c.xpath('.//*[local-name()="explicitMember" or local-name()="typedMember"]'):continue
                    if c.xpath('.//*[local-name()="startDate"]/text()')!=[start] or c.xpath('.//*[local-name()="endDate"]/text()')!=[end]:continue
                    assert int(c.xpath('.//*[local-name()="identifier"]/text()')[0])==cik
                    matches.append(node)
                assert len(matches)==1;n=matches[0];assert Decimal(n.text)==f['val']
                inline=doc.xpath('//*[@id=$id]',id=n.get('id'));assert len(inline)==1;v=inline[0]
                assert v.get('name').split(':')[-1]==TAG and Decimal(''.join(v.itertext()).replace(',',''))*10**int(v.get('scale'))==f['val']
                tables=v.xpath('ancestor::table');assert tables
                table=' '.join(tables[-1].text_content().split())
                ev.update(primary_sha256=sha(primary),instance_sha256=sha(instance),comparative_accession=acc,inline_id=n.get('id'),inline_scale=v.get('scale'),table_text=table,table_sha256=sha(table.encode()),status='ORIGINAL_ACCESSION_COMPANYFACTS_AND_CURRENT_INLINE_VERIFIED')
            else:ev['status']='ORIGINAL_ACCESSION_COMPANYFACTS_AND_LATER_FILINGS_AGREE'
            observations.append(ev)
    return dict(schema='historical_shares_source_v1',receipt_sha256=RECEIPT,s1_sha256=S1,observations=observations,fresh_sec_fetch=False,limitations=['FY2022 verified through archived SEC Companyfacts at original and later accessions; original FY2022 inline document not in this archive','Share counts are not organic-growth measures; IP row-basis review remains open'],economic_clearance=False,buy_add_allowed=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--s1',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    Path(a.output).write_text(json.dumps(build(a.archive,Path(a.s1).read_bytes()),indent=2)+'\n')
