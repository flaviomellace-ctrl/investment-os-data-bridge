"""Read pinned archived SEC documents; optional archive verifier requires lxml."""
import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from lxml import etree, html

def sha(data):
    return hashlib.sha256(data).hexdigest()

def require(ok, message):
    if not ok:
        raise ValueError(message)

class Sources:
    def __init__(self, directory, receipt_sha, run, commit):
        self.directory = Path(directory)
        require(self.directory.is_dir() and not self.directory.is_symlink(), 'unsafe source directory')
        rp = self.directory / 'PRIMARY_RECEIPT.json'
        require(rp.is_file() and not rp.is_symlink(), 'unsafe receipt')
        body = rp.read_bytes()
        require(sha(body) == receipt_sha, 'source receipt pin mismatch')
        self.receipt = json.loads(body)
        r = self.receipt
        require(r['schema'] == 'v43_primary_acquisition_v1' and r['github_run_id'] == str(run) and r['github_sha'] == commit, 'source acquisition identity mismatch')
        require(r['acquisition_complete'] is True and r['errors'] == [], 'source acquisition incomplete')
        require(all(r[k] is False for k in ('economic_clearance', 'candidate_promoted', 'buy_add_allowed')), 'source receipt claims clearance')
        self.entries = {}
        for e in r['entries']:
            rel = Path(e['file'])
            require(e['status'] == 'FETCHED' and not rel.is_absolute() and '..' not in rel.parts, 'unsafe or missing source')
            p = self.directory / rel
            require(p.is_file() and not p.is_symlink(), 'unsafe source file')
            data = p.read_bytes()
            require(sha(data) == e['sha256'] and len(data) == e['bytes'], 'source hash/size mismatch')
            require(e['file'] not in self.entries, 'duplicate source')
            self.entries[e['file']] = e
        require({p.relative_to(self.directory).as_posix() for p in (self.directory / 'raw').iterdir()} == set(self.entries), 'source inventory mismatch')

    def body(self, accession, role):
        entries = [e for e in self.entries.values() if e['role'] == role and e['identity'].get('accession') == accession]
        require(len(entries) == 1, 'primary document missing or ambiguous')
        e = entries[0]
        b = (self.directory / e['file']).read_bytes()
        require(sha(b) == e['sha256'] and len(b) == e['bytes'], 'source changed after initial verification')
        encoding = next((v for k, v in e.get('response_headers', {}).items() if k.lower() == 'content-encoding'), '')
        return gzip.decompress(b) if encoding.lower() == 'gzip' else b

    def facts(self, accession, cik, concept, end, start=None):
        root = etree.fromstring(self.body(accession, 'EXTRACTED_INSTANCE'), etree.XMLParser(resolve_entities=False, no_network=True))
        ctx = {x.get('id'): x for x in root.xpath("//*[local-name()='context']")}
        result = []
        for n in root.xpath("//*[local-name()=$name]", name=concept):
            q = etree.QName(n)
            if not (q.namespace or '').startswith('http://fasb.org/us-gaap/'):
                continue
            c = ctx.get(n.get('contextRef'))
            if c is None or c.xpath(".//*[local-name()='explicitMember' or local-name()='typedMember']"):
                continue
            def value(name):
                return ''.join(c.xpath('.//*[local-name()=$n]/text()', n=name))
            if value('identifier').lstrip('0') != str(cik) or (value('endDate') or value('instant')) != end:
                continue
            if start is not None and value('startDate') != start:
                continue
            v = Decimal(n.text or '')
            require(v.is_finite(), 'nonfinite primary fact')
            result.append({'id': n.get('id'), 'concept': concept, 'value': str(v), 'decimals': n.get('decimals'), 'unit_ref': n.get('unitRef'), 'context_ref': n.get('contextRef'), 'start': value('startDate'), 'end': end, 'cik': cik, 'accession': accession})
        return result

    def one(self, accession, cik, concept, end, start=None):
        fs = self.facts(accession, cik, concept, end, start)
        require(fs and len({x['value'] for x in fs}) == 1, 'primary fact missing or conflicting')
        return fs[0]

    def table(self, fact, required_caption):
        document = html.fromstring(self.body(fact['accession'], 'PRIMARY_IXBRL'))
        nodes = document.xpath('//*[@id=$id]', id=fact['id'])
        require(len(nodes) == 1, 'inline fact id missing or duplicate')
        n = nodes[0]
        require(n.get('name', '').split(':')[-1] == fact['concept'] and n.get('contextref') == fact['context_ref'], 'inline and instance identity differ')
        v = Decimal(''.join(n.itertext()).replace(',', '').strip()) * (Decimal(10) ** int(n.get('scale', '0')))
        if n.get('sign') == '-':
            v = -v
        require(v == Decimal(fact['value']), 'inline and instance values differ')
        tables = n.xpath('ancestor::table')
        require(tables, 'fact has no scoped table')
        text = ' '.join(tables[-1].text_content().split())
        require(required_caption in text, 'required table caption missing')
        return {'caption_required': required_caption, 'table_text': text, 'table_text_sha256': sha(text.encode()), 'inline_scale': n.get('scale', '0'), 'fact': fact}
