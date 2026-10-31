import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src import audit_br04_data09 as audit
from src import rebase_br04_data09 as rebase

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'data/research/br04-data09'

class PrimaryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate,_=rebase.reconstruct((ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes(),(DIR/'manifest.json').read_bytes())
        cls.evidence=(DIR/'primary_evidence.json').read_bytes()

    def test_all_primary_links_reconcile(self):
        result=audit.audit(self.candidate,self.evidence)
        self.assertEqual((result['aggregate_links'],result['fact_links']),(20,28))
        self.assertEqual(result,json.loads((DIR/'primary_component_links.json').read_text()))
        self.assertFalse(result['full_s2_passed'])
        self.assertFalse(result['candidate_promoted'])

    def test_byte_tampering_rejected(self):
        for candidate,evidence in [(self.candidate+b' ',self.evidence),(self.candidate,self.evidence+b' ')]:
            with self.assertRaisesRegex(ValueError,'hash'):audit.audit(candidate,evidence)

    def test_bad_provenance_rejected_even_if_repinned(self):
        for mutation,error in [
            (lambda p:p['debt_evidence']['companies'][0].update(accession='wrong'),'filing mismatch'),
            (lambda p:p['debt_evidence']['companies'][0]['facts']['long'].update(instant='2024-12-31'),'period mismatch'),
            (lambda p:p['debt_evidence']['companies'][0]['facts']['long'].update(unit='EUR'),'unit/value'),
            (lambda p:p['debt_evidence']['companies'][0]['facts']['long'].update(value_usd=1),'aggregate mismatch'),
            (lambda p:p['debt_evidence']['companies'][0]['facts']['long'].update(coverage=['short']),'overlapping'),
            (lambda p:p['debt_evidence']['companies'][0]['facts']['long'].update(kind='asset'),'nonliability'),
            (lambda p:p['lease_evidence'][0]['lease_observations'][0]['interest'].update(value_usd=0),'lease present value'),
        ]:
            with self.subTest(error=error):
                p=json.loads(self.evidence);mutation(p);b=json.dumps(p).encode()
                with patch.object(audit,'EVIDENCE_SHA',hashlib.sha256(b).hexdigest()):
                    with self.assertRaisesRegex(ValueError,error):audit.audit(self.candidate,b)
