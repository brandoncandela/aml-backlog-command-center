"""Tests for onboarding, identity resolution, case priority and the capacity forecast."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import build  # noqa: E402
import cases  # noqa: E402
import forecast  # noqa: E402
import ingest  # noqa: E402
import resolve  # noqa: E402


class Onboarding(unittest.TestCase):
    def test_money_formats_from_every_source(self):
        self.assertEqual(ingest.parse_money("12,345.67"), 12345.67)
        self.assertEqual(ingest.parse_money("$12,345"), 12345.0)
        self.assertEqual(ingest.parse_money("$4.2k"), 4200.0)
        self.assertIsNone(ingest.parse_money(""))

    def test_mixed_date_formats_and_bad_dates(self):
        self.assertEqual(ingest.parse_date("2026/07/03", ["%Y-%m-%d", "%Y/%m/%d"]), date(2026, 7, 3))
        with self.assertRaises(ingest.Rejected):
            ingest.parse_date("00/00/0000", ["%m/%d/%Y"])

    def test_names_normalize_across_orders(self):
        self.assertEqual(ingest.normalize_name("Anderson, Luis E.", "last_first"), "luis e anderson")
        self.assertEqual(ingest.normalize_name("LUIS E ANDERSON"), "luis e anderson")

    def test_new_source_is_onboarded_with_config_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "case_mgmt.csv").write_text(
                "id;client;who;flag;when;usd;open\n"
                "1;00012345;Doe, Jane;Smurfing;17.10.2026;1.000;Y\n"
                "1;00012345;Doe, Jane;Smurfing;17.10.2026;1.000;Y\n"
                "2;00012346;Roe, Rick;Smurfing;bad;5;Y\n"
                "3;00012347;Poe, Ann;Smurfing;18.10.2026;7;N\n")
            config = {"source": "case_mgmt", "label": "Case tool", "file": "case_mgmt.csv", "format": "delimited",
                      "delimiter": ";", "dedupe_on": ["alert_id"], "fields": {
                          "alert_id": {"column": "id"}, "customer_ref": {"column": "client", "ref_type": "cif"},
                          "name": {"column": "who", "name_order": "last_first"},
                          "scenario": {"column": "flag", "map": {"Smurfing": "structuring"}},
                          "alert_date": {"column": "when", "date_formats": ["%d.%m.%Y"]},
                          "amount": {"column": "usd", "parse": "money"}, "status": {"column": "open", "open_values": ["Y"]}}}
            rows, report = ingest.load_source(config, folder)
        self.assertEqual([r["alert_id"] for r in rows], ["1"])
        self.assertEqual(rows[0]["scenario"], "structuring")
        self.assertEqual(rows[0]["name"], "jane doe")
        self.assertEqual((report["duplicates"], report["closed"], report["rejected"]), (1, 1, {"unreadable date": 1}))


CUSTOMERS = [
    {"CIF": "00000001", "name": "michael a smith", "DOB": "1980-01-01", "accounts": ["1111222233"]},
    {"CIF": "00000002", "name": "maria lopez", "DOB": "1975-05-05", "accounts": ["4444555566"]},
    {"CIF": "00000003", "name": "maria lopez", "DOB": "1990-09-09", "accounts": ["7777888899"]},
    {"CIF": "00000004", "name": "nadia king", "DOB": "1966-06-06", "accounts": ["1212343456"]},
]


def alert(**kw):
    base = {"alert_id": "A", "customer_ref": None, "ref_type": None, "name": "", "dob": None}
    return base | kw


class Resolution(unittest.TestCase):
    def setUp(self):
        self.r = resolve.Resolver(CUSTOMERS, {"P9": "00000001"})

    def test_strong_identifiers_resolve_with_full_confidence(self):
        self.assertEqual(self.r.resolve(alert(customer_ref="P9", ref_type="party_key"))["method"], "crosswalk")
        self.assertEqual(self.r.resolve(alert(customer_ref="1".zfill(8), ref_type="cif"))["cif"], "00000001")
        self.assertEqual(self.r.resolve(alert(customer_ref="4444555566", ref_type="account"))["cif"], "00000002")

    def test_masked_account_needs_matching_name(self):
        hit = self.r.resolve(alert(customer_ref="****2233", ref_type="account", name="mike smith"))
        self.assertEqual((hit["cif"], hit["method"]), ("00000001", "masked_account_name"))
        miss = self.r.resolve(alert(customer_ref="****2233", ref_type="account", name="someone else"))
        self.assertIsNone(miss["cif"])

    def test_dob_separates_two_customers_with_the_same_name(self):
        hit = self.r.resolve(alert(name="maria lopez", dob="1990-09-09"))
        self.assertEqual((hit["cif"], hit["method"]), ("00000003", "name_dob"))

    def test_shared_name_without_identifier_is_ambiguous_not_guessed(self):
        hit = self.r.resolve(alert(name="maria lopez"))
        self.assertEqual((hit["cif"], hit["method"]), (None, "ambiguous"))
        self.assertEqual(len(hit["candidates"]), 2)

    def test_name_only_match_goes_to_review(self):
        hit = self.r.resolve(alert(name="nadia king"))
        self.assertEqual(hit["method"], "name_only")
        self.assertLess(hit["confidence"], resolve.AUTO_ACCEPT)


class CasePriority(unittest.TestCase):
    def make(self, risk, ages, scenarios, sources=("actimize",)):
        alerts = [{"alert_id": str(i), "source": sources[i % len(sources)], "scenario": s, "amount": 5000,
                   "auto_accepted": True, "resolution": {"cif": "1"},
                   "alert_date": (cases.AS_OF.toordinal() - age)} for i, (age, s) in enumerate(zip(ages, scenarios))]
        for a in alerts:
            a["alert_date"] = date.fromordinal(a["alert_date"]).isoformat()
        customer = [{"CIF": "1", "FULL_NAME": "Test", "SEGMENT": "retail", "RISK_RATING": risk}]
        return cases.build_cases(alerts, customer)[0]

    def test_all_alerts_for_a_customer_form_one_case(self):
        case = self.make("L", [10, 20, 30], ["large_cash"] * 3)
        self.assertEqual(len(case["alerts"]), 3)
        self.assertEqual(case["oldest_age_days"], 30)

    def test_score_is_the_sum_of_its_parts_and_sets_the_tier(self):
        case = self.make("H", [200, 150], ["structuring", "large_cash"], sources=("actimize", "legacy_rules"))
        self.assertEqual(case["priority_score"], sum(p for _, p in case["score_parts"]))
        self.assertEqual(case["tier"], "P1")
        self.assertTrue(case["sla_breached"])

    def test_low_risk_recent_single_alert_is_p3(self):
        case = self.make("L", [5], ["dormant_reactivation"])
        self.assertEqual(case["tier"], "P3")
        self.assertFalse(case["sla_breached"])


class Forecast(unittest.TestCase):
    def test_working_days_skip_weekends_and_holidays(self):
        days = forecast.working_days(date(2026, 12, 24), 3)
        self.assertEqual(days, [date(2026, 12, 24), date(2026, 12, 28), date(2026, 12, 29)])

    def test_analysts_needed_is_the_minimum_that_meets_the_deadline(self):
        total = 150_000
        n = forecast.analysts_needed(total)
        self.assertLessEqual(forecast.clear_date(total, n), forecast.DEADLINE)
        self.assertGreater(forecast.clear_date(total, n - 1), forecast.DEADLINE)

    def test_grouping_saves_time_only_when_customers_have_several_alerts(self):
        single = {"alerts": [{"scenario": "large_cash"}], "risk_rating": "L", "tier": "P3"}
        double = {"alerts": [{"scenario": "large_cash"}] * 2, "risk_rating": "L", "tier": "P3"}
        one = forecast.effort([single], 0)
        two = forecast.effort([double], 0)
        a = forecast.ASSUMPTIONS
        self.assertAlmostEqual(one["case_level_minutes"] - one["alert_level_minutes"], a["case_base_minutes"] - a["alert_minutes"], delta=1)
        self.assertLess(two["case_level_minutes"], two["alert_level_minutes"])


class FullBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build.build()

    def test_automatic_matches_are_correct_against_the_answer_key(self):
        self.assertGreaterEqual(self.data["resolution"]["accuracy"]["auto_precision"], 0.995)

    def test_every_loaded_alert_is_in_a_case_or_the_review_queue(self):
        in_cases = sum(len(c["alerts"]) for c in self.data["cases"])
        self.assertEqual(in_cases + len(self.data["review_queue"]), self.data["summary"]["alerts"])

    def test_case_level_needs_fewer_analysts(self):
        f = self.data["forecast"]
        self.assertLess(f["analysts_needed_case_level"], f["analysts_needed_alert_level"])

    def test_build_is_deterministic(self):
        self.assertEqual(json.dumps(build.build(), sort_keys=True), json.dumps(self.data, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
