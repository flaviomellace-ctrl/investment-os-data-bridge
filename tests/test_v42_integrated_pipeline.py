"""Integration tests for the V4.2 orchestrator. Synthetic development fixtures only.

These fixtures are development examples: they are NOT the R11 hidden controls.
"""
import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import v42_integrated_pipeline as ip  # noqa: E402

COMP = ip.load_components()
PRIMARY = dict(source_type="PRIMARY", source_url_or_accession="dev-synthetic-doc", filing_date="2026-01-01",
               classification_as_of="2026-01-01", evidence_excerpt_or_hash="dev-hash")


def row(key, **over):
    r = dict(ticker=key, sic="2000", core_metric_coverage_pct="100", operating_margin="0.22", fcf_margin="0.18",
             net_margin="0.15", roe_simple="0.2", roic="0.19", annual_revenue="1000", annual_net_income="150",
             annual_operating_cash_flow="200", annual_capex="20", annual_equity="700", annual_assets="1500",
             net_debt_to_ocf="1.2", diluted_shares_yoy="-0.01", net_income_yoy="0.1", revenue_cagr3="0.11",
             opinc_cagr3="0.12", fcf_cagr3="0.10", fcf_per_share_cagr3="0.11", operating_margin_std_4y="0.05",
             annual_sbc="10", sbc_to_revenue="0.01", market_cap="2500", market_price="25", market_data_status="PRESENT",
             buyback_accretion="1.6", payout_ratio="0.3", interest_coverage="9", total_debt="300",
             cash_and_equivalents="60", operating_lease_liabilities="40", annual_operating_income="220",
             data_quality_flags="", annual_period="20251231")
    r.update({k: str(v) for k, v in over.items()})
    return r


def clean_evidence(**br09):
    base = dict(agency_or_net_presentation=False, intermediation_language=False, cogs=dict(value=600),
                two_sided_intermediation=False, revenue_linked_to_underlying_volume=False,
                company_reports_underlying_volume=False, evidence=PRIMARY)
    base.update(br09)
    return dict(br09=base,
                cash_quality=dict(working_capital_anomaly=False, reserve_or_float_dependency=False,
                                  tax_timing_anomaly=False, noncash_revaluation_flag=False, normalization_complete=False),
                commitments=dict(items=[], inventory_complete=True),
                leverage=dict(depreciation_amortization=dict(value=50)),
                lane_flags=dict(quality_flags=[], cyclical_rebound_flag=False),
                economic_clearance=dict(independent=True, reference="dev-synthetic-clearance"))


def run(rows, entities=None, **kw):
    return ip.run(rows, dict(schema=ip.EVIDENCE_SCHEMA, entities=entities or {}), components=COMP, **kw)


def one(result, key):
    return next(r for r in result["results"] if r["entity_key"] == key)


class IntegratedPipelineTests(unittest.TestCase):
    def test_pins_cover_the_frozen_engine_manifest(self):
        import json
        m = json.loads((ROOT / "docs/V4_2_ENGINE_MANIFEST.json").read_text())
        pins = {k: v[1] for k, v in ip.FROZEN_COMPONENTS.items()}
        self.assertEqual(pins["engine"], m["v4_2_engine_sha256"])
        self.assertEqual(pins["classifier"], m["marketplace_classifier_sha256"])
        self.assertEqual(pins["lane"], m["inflection_lane_sha256"])
        self.assertEqual(pins["cash"], m["cash_quality_commitments_sha256"])

    def test_tampered_component_is_rejected(self):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / "src"
            shutil.copytree(ROOT / "src", dst, ignore=shutil.ignore_patterns("__pycache__", "*.zip"))
            target = dst / "inflection_lane_v42.py"
            target.write_text(target.read_text().replace("MIN_FCF_CAGR3 = 0.15", "MIN_FCF_CAGR3 = 0.10"))
            with self.assertRaises(ip.IntegrationError):
                ip.load_components(dst)

    def test_br09_thresholds_equal_r10d_frozen_values(self):
        text = (ROOT / "src/r10d_real_overlays.py").read_text()
        self.assertEqual(float(re.search(r"^MAX_COGS_TO_REVENUE=([0-9.]+)", text, re.M).group(1)), ip.MAX_COGS_TO_REVENUE)
        self.assertEqual(float(re.search(r"^MAX_CAPEX_TO_REVENUE=([0-9.]+)", text, re.M).group(1)), ip.MAX_CAPEX_TO_REVENUE)

    def test_orchestrator_has_no_entity_literal_or_own_scoring(self):
        import json
        src = (ROOT / "src/v42_integrated_pipeline.py").read_text()
        cases = {r["case_id"] for r in json.loads((ROOT / "docs/evidence/economic_registry_verified.json").read_text())["records"]}
        for token in cases | {"UBER"}:
            self.assertIsNone(re.search(r"['\"]%s['\"]" % re.escape(token), src), token)
        self.assertNotIn("def bqs", src)
        self.assertNotIn("def ios", src)

    def test_deterministic_and_never_live(self):
        rows = [row("DEV-A"), row("DEV-B", annual_sbc="")]
        a = ip.canonical_json(run(copy.deepcopy(rows)))
        b = ip.canonical_json(run(list(reversed(copy.deepcopy(rows)))))
        self.assertEqual(a, b)
        self.assertEqual(run(rows)["buy_add_allowed_rows"], 0)

    def test_missing_evidence_is_provisional_not_clean(self):
        r = one(run([row("DEV-A")]), "DEV-A")
        self.assertEqual(r["br09"]["classification_status"], "PROVISIONAL")
        self.assertEqual(r["module_final"], r["module_original"])
        self.assertEqual(r["overlay"]["cash_quality_gate"], "NOT_REVIEWED_EVIDENCE_MISSING")
        self.assertFalse(r["decision"]["allowed_under_hypothetical_live_state"])

    def test_missing_owner_cash_input_is_not_zero(self):
        r = one(run([row("DEV-A", annual_sbc="")]), "DEV-A")
        self.assertIsNone(r["ios"])
        self.assertIn("SBC", r["ios_gate"])

    def test_verified_marketplace_is_rerouted_with_provenanced_kpis(self):
        mp = lambda v: dict(value=v, period="FY", scope="GLOBAL", definition="dev", source="dev")
        ev = clean_evidence(agency_or_net_presentation=True, intermediation_language=True, cogs=dict(value=300),
                            two_sided_intermediation=True, revenue_linked_to_underlying_volume=True,
                            company_reports_underlying_volume=True,
                            kpis=dict(underlying_volume=mp(6000), net_revenue=mp(1000), ebitda=mp(240), fcf=mp(170)))
        r = one(run([row("DEV-M")], {"DEV-M": ev}), "DEV-M")
        self.assertEqual(r["module_final"], "MARKETPLACE_NETWORK")
        self.assertEqual(r["ios_variant"], "IOS_GENERAL")
        self.assertAlmostEqual(r["marketplace_kpis"]["take_rate"], 1000 / 6000)
        self.assertIsNone(r["marketplace_kpis"]["retention"])

    def test_platform_language_alone_keeps_original_module(self):
        ev = clean_evidence(intermediation_language=True)
        r = one(run([row("DEV-S", sic="7372")], {"DEV-S": ev}), "DEV-S")
        self.assertEqual((r["module_final"], r["br09"]["classification_status"]), ("SOFTWARE", "VERIFIED"))

    def test_unquantified_material_commitment_blocks(self):
        ev = clean_evidence()
        ev["commitments"]["items"] = [dict(category="PURCHASE_OBLIGATIONS", amount=None, status="MISSING", material=True,
                                           already_in_debt=False, source="dev", data_as_of="2025-12-31", definition="dev")]
        r = one(run([row("DEV-C")], {"DEV-C": ev}), "DEV-C")
        self.assertEqual(r["overlay"]["commitments_gate"], "INVESTIGARE")
        self.assertFalse(r["decision"]["allowed_under_hypothetical_live_state"])

    def test_only_fully_cleared_entity_is_gate_eligible_and_still_not_live(self):
        r = one(run([row("DEV-A")], {"DEV-A": clean_evidence()}), "DEV-A")
        self.assertEqual(r["decision"]["unresolved_reasons"], [])
        self.assertTrue(r["decision"]["allowed_under_hypothetical_live_state"])
        self.assertFalse(r["decision"]["buy_add_allowed"])

    def test_open_registry_case_blocks_even_with_clean_overlays(self):
        reg = [dict(flag_id="DEV-A_X", case_id="DEV-A", economic_case_closed=False)]
        r = one(run([row("DEV-A")], {"DEV-A": clean_evidence()}, economic_registry=reg), "DEV-A")
        self.assertIn("UNRESOLVED_ECONOMIC_CASE", r["decision"]["unresolved_reasons"])

    def test_conflict_and_bad_inputs(self):
        r = one(run([row("DEV-A", roic="CONFLICTING")], {"DEV-A": clean_evidence()}), "DEV-A")
        self.assertTrue(r["data_conflict"])
        self.assertFalse(r["decision"]["allowed_under_hypothetical_live_state"])
        with self.assertRaises(ip.IntegrationError):
            run([row("DEV-A"), row("DEV-A")])
        with self.assertRaises(ip.IntegrationError):
            run([row("DEV-A")], {"DEV-Z": clean_evidence()})

    def test_engine_growth_guard_receives_its_inputs(self):
        # operating income +5% but net income +90%: the engine's own base-effect guard must fire
        flagged = row("DEV-G", net_income_yoy="0.9", prior_operating_income="209.5", revenue_cagr3="0.16",
                      fcf_cagr3="0.3", fcf_per_share_cagr3="0.27")
        plain = row("DEV-H", prior_operating_income="200", revenue_cagr3="0.16", fcf_cagr3="0.3", fcf_per_share_cagr3="0.27")
        res = run([flagged, plain])
        g, h = one(res, "DEV-G"), one(res, "DEV-H")
        self.assertEqual(g["growth_flags"], ["BASE_EFFECT_SUSPECTED"])
        self.assertFalse(g["lane_i"]["high_confidence"])
        self.assertTrue(h["lane_i"]["high_confidence"])
        self.assertEqual((g["bqs"], g["ios"]), (h["bqs"], h["ios"]))

    def test_mixed_basis_guard_is_flag_driven(self):
        r = one(run([row("DEV-X", data_quality_flags="ANY_MIXED_CONTINUING_DISCONTINUED_BASIS", fcf_margin="", net_margin="")]), "DEV-X")
        self.assertEqual(r["data_guards"], ["MIXED_BASIS_RATIOS_SUPPRESSED"])
        with self.assertRaises(ip.IntegrationError):
            run([row("DEV-Y", data_quality_flags="ANY_MIXED_CONTINUING_DISCONTINUED_BASIS")])


if __name__ == "__main__":
    unittest.main()
