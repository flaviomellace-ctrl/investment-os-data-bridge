import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from lxml import html
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from r10f_verify_source_corrections import context_record, fact_value, verify_fact, verify_registry

FIXTURE = '''<html><body>
<xbrli:context id="annual"><xbrli:entity><xbrli:identifier>123</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:startdate>2025-01-01</xbrli:startdate><xbrli:enddate>2025-12-31</xbrli:enddate></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
<ix:nonfraction id="one" name="example:Amount" contextref="annual" unitref="usd" scale="6" format="ixt:num-dot-decimal">1,234.5</ix:nonfraction>
</body></html>'''


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.root = html.fromstring(FIXTURE)
        self.element = self.root.get_element_by_id("one")
        self.spec = {"id": "one", "attributes": dict(self.element.attrib),
                     "context": context_record(self.root, "annual"),
                     "expected_value_usd": "1234500000", "coefficient": 1}

    def test_scale_and_signed_value(self):
        self.assertEqual(verify_fact(self.root, self.spec, "2025-12-31"), 1234500000)
        self.element.set("sign", "-")
        self.assertEqual(fact_value(self.element), -1234500000)

    def test_zero_requires_documented_transform(self):
        self.element.text = "—"
        with self.assertRaisesRegex(ValueError, "INVALID_NUMERIC"):
            fact_value(self.element)
        self.element.set("format", "ixt:fixed-zero")
        self.assertEqual(fact_value(self.element), 0)
        self.element.set("xsi:nil", "true")
        with self.assertRaisesRegex(ValueError, "NIL_IS_NOT_ZERO"):
            fact_value(self.element)

    def test_value_conflict_stops(self):
        self.element.text = "1,235.5"
        with self.assertRaisesRegex(ValueError, "VALUE_CHANGED"):
            verify_fact(self.root, self.spec, "2025-12-31")

    def test_duplicate_fact_stops(self):
        self.element.getparent().append(copy.deepcopy(self.element))
        with self.assertRaisesRegex(ValueError, "FACT_NOT_UNIQUE"):
            verify_fact(self.root, self.spec, "2025-12-31")

    def test_changed_dimensions_stop(self):
        context = self.root.get_element_by_id("annual")
        context.append(html.fromstring('<xbrldi:explicitmember dimension="example:Scope">example:Segment</xbrldi:explicitmember>'))
        with self.assertRaisesRegex(ValueError, "CONTEXT_SCOPE_CHANGED"):
            verify_fact(self.root, self.spec, "2025-12-31")

    def test_wrong_period_and_quarter_stop(self):
        with self.assertRaisesRegex(ValueError, "PERIOD_MISMATCH"):
            verify_fact(self.root, self.spec, "2024-12-31")
        self.root = html.fromstring(FIXTURE.replace("2025-01-01", "2025-10-01"))
        self.spec["context"] = context_record(self.root, "annual")
        with self.assertRaisesRegex(ValueError, "NONANNUAL_DURATION"):
            verify_fact(self.root, self.spec, "2025-12-31")

    def test_currency_mismatch_stops(self):
        self.root = html.fromstring(FIXTURE.replace("iso4217:USD", "iso4217:EUR"))
        with self.assertRaisesRegex(ValueError, "NOT_USD_UNIT"):
            verify_fact(self.root, self.spec, "2025-12-31")

    def test_source_tampering_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.html"
            path.write_text(FIXTURE)
            registry = {"items": [{"source_file": path.name, "source_sha256": "0" * 64}]}
            with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
                verify_registry(registry, Path(folder))


if __name__ == "__main__":
    unittest.main()
