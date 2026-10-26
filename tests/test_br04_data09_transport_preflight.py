import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import rebase_br04_data09 as rebase
import br04_data09_runtime as runtime
import br04_data09_transport as transport
import br04_data09_preflight as engine

ROOT=Path(__file__).resolve().parents[1]

class TransportPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.directory=self.root/'data/research/br04-data09'
        self.directory.mkdir(parents=True)
        for name in [runtime.RECEIPT,'.github/workflows/br04-s4-engine-preflight.yml','data/current/sp500_fundamentals.csv']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        data,_=rebase.reconstruct((ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes(),(ROOT/'data/research/br04-data09/manifest.json').read_bytes())
        (self.directory/'RESEARCH_NOT_PROMOTED.csv').write_bytes(data)
        runtime.restore_runtime(self.root)
        self.current=self.root/'data/current/sp500_fundamentals.csv'
        self.before=self.current.read_bytes()

    def run_transport(self):
        with patch.object(transport,'ROOT',self.root),patch.object(transport,'CURRENT',self.current),contextlib.redirect_stdout(io.StringIO()):
            return transport.main()

    def run_engine(self):
        with patch.object(engine,'ROOT',self.root),patch.object(engine,'ENGINE_PATH',self.directory/'runtime/v4_scoring.py'),contextlib.redirect_stdout(io.StringIO()):
            return engine.main()

    def test_full_pipeline_and_canonical_unchanged(self):
        self.assertEqual(self.run_transport(),0)
        self.assertEqual(self.run_engine(),0)
        report=json.loads((self.directory/'research_engine.json').read_text())
        self.assertEqual((report['rows_read'],report['columns'],report['exceptions']),(504,285,0))
        self.assertTrue(report['transport_validation']['reassembled_byte_identical'])
        self.assertEqual(report['phase'],'S4_RESEARCH')
        self.assertFalse(report['candidate_promoted'])
        self.assertEqual(self.current.read_bytes(),self.before)
        self.assertFalse((self.root/'data/staging').exists())

    def test_wrong_base_blocks_transport(self):
        self.current.write_bytes(self.before+b' ')
        with self.assertRaisesRegex(SystemExit,'BASE_CHANGED'):self.run_transport()

    def test_wrong_candidate_blocks_transport(self):
        p=self.directory/'RESEARCH_NOT_PROMOTED.csv';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(SystemExit,'SHA candidato'):self.run_transport()

    def test_wrong_receipt_blocks_transport(self):
        p=self.root/runtime.RECEIPT;p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'receipt hash'):self.run_transport()

    def test_corrupted_chunk_blocks_engine(self):
        self.run_transport()
        index=json.loads((self.directory/'fundamentals_chunks.json').read_text())
        p=self.directory/index['parts'][0]['filename'];p.write_bytes(p.read_bytes().replace(b'CVX',b'CVY',1)+b' ')
        with self.assertRaises(SystemExit):self.run_engine()

    def test_corrupted_engine_blocks_preflight(self):
        self.run_transport()
        p=self.directory/'runtime/v4_scoring.py';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(SystemExit,'ENGINE_MD5'):self.run_engine()

    def test_wrong_part_range_blocks_preflight(self):
        self.run_transport()
        p=self.directory/'fundamentals_chunks.json';index=json.loads(p.read_text());index['parts'][0]['row_start_1_based']=2;p.write_text(json.dumps(index))
        with self.assertRaisesRegex(SystemExit,'TRANSPORT'):self.run_engine()
