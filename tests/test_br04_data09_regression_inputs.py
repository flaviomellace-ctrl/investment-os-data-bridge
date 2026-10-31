import shutil
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import br04_data09_regression as extension

ROOT=Path(__file__).resolve().parents[1]

class ResearchInputTests(unittest.TestCase):
    def test_isolation_source_preservation_and_explicit_reclassification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=Path('data/staging/br04/40122845921')
            shutil.copytree(ROOT/source,root/source)
            research=Path('data/research/br04-data09')
            (root/research).mkdir(parents=True)
            for name in ['manifest.json','primary_evidence.json']:
                shutil.copyfile(ROOT/research/name,root/research/name)
            original={p.relative_to(root):p.read_bytes() for p in (root/source).rglob('*') if p.is_file()}
            result=extension.prepare(root)
            self.assertEqual(result['retained_fsds_components'],3937)
            self.assertEqual(result['superseded_fsds_components'],6)
            self.assertEqual(len(result['primary_keys']),28)
            self.assertEqual(len(result['components']),3965)
            for path,data in original.items():self.assertEqual((root/path).read_bytes(),data)
            self.assertEqual(list((root/'data/staging/br04').iterdir()),[root/source])
            loans=[r for r in result['custom'] if r['ticker']=='JPM' and r['tag'].startswith('FinancingReceivable')]
            self.assertEqual(len(loans),1)
            self.assertEqual(loans[0]['assigned_class'],'CUSTOM_NON_DEBT')
            self.assertEqual(result['metadata']['candidate_sha256'],extension.primary.CANDIDATE_SHA)
            self.assertNotEqual(result['metadata']['candidate_sha256'],extension.rebase.INPUT_SHA)
            row=next(r for r in result['components'] if r.get('source_kind'))
            for field in ['primary_fact_id','value','adsh','tag','fsds_version','stmt']:
                with self.subTest(field=field):
                    altered=dict(row);altered[field]='tampered'
                    self.assertNotIn(extension.component_identity(altered),result['primary_keys'])
