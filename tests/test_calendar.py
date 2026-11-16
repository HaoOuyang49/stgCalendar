"""Public calendar conventions, source selection and observable boundary regressions."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from stg_calendar import (
    EstimatedTermConsentRequired, TermPrecisionConsentRequired, calendar_at,
    coverage, day_hour_pillars, get_term, local_clock, resolve_windows_report, terms_for_year,
)
from stg_calendar import calendar, pmo_terms


HAS_CALENDAR = importlib.util.find_spec("lunar_python") is not None


class OfficialTables(unittest.TestCase):
    def test_coverage_reports_local_records_without_an_accuracy_claim(self):
        result = coverage()
        self.assertEqual(result["sources"]["pmo"]["record_count"], 3052)
        self.assertEqual(result["sources"]["pmo"]["complete_years"], list(range(1900, 2027)))
        self.assertEqual(len(result["sources"]["pmo"]["partial_years"]["2027"]), 4)
        self.assertEqual(result["sources"]["hko"]["complete_years"], [2027])
        self.assertIsNone(result["validation"]["accuracy_bound_seconds"])

    def test_every_record_has_a_valid_month_order_and_publication(self):
        combined = calendar.HKO_TERMS | calendar.OFFICIAL_TERMS
        self.assertEqual(len(combined), 3072)
        for year in range(1900, 2028):
            times = [combined[year, name] for name in pmo_terms.TERM_MONTH]
            self.assertEqual(len(times), 24)
            for (name, month), moment in zip(pmo_terms.TERM_MONTH.items(), times):
                self.assertEqual((moment.year, moment.month), (year, month))
                self.assertEqual(moment.utcoffset(), timedelta(hours=8))
                self.assertEqual(moment.second, 0)
            self.assertTrue(all(timedelta(days=10) < b - a < timedelta(days=20)
                                for a, b in zip(times, times[1:])))
            self.assertTrue(pmo_terms.publication_for(min(year, 2026))["url"].startswith("https://pmo.cas.cn/"))

    def test_official_lookup_does_not_call_the_optional_calculator(self):
        with patch.object(calendar, "lunar_at", side_effect=AssertionError("calculator used")):
            term = get_term(2026, "立冬")
            year = terms_for_year(2027)
        self.assertEqual(term["time"], "2026-11-07T17:52:00+08:00")
        self.assertEqual(term["source"]["provider"], "pmo")
        self.assertEqual(len(year["terms"]), 24)
        self.assertEqual([t["source"]["provider"] for t in year["terms"]], ["pmo"] * 4 + ["hko"] * 20)

    def test_publication_edition_matches_the_actual_table(self):
        old = get_term(1917, "大雪")
        self.assertEqual(old["time"], "1917-12-08T00:01:00+08:00")
        self.assertEqual(old["source"]["publication"]["kind"], "historical_calendar")
        spring = get_term(2027, "立春")
        self.assertEqual(spring["source"]["publication"]["edition"], "2026")
        self.assertFalse(spring["data_coverage"]["complete_requested_year"])

    def test_pmo_precedes_hko_and_hko_fills_a_missing_record(self):
        self.assertEqual(get_term(2027, "立春")["source"]["provider"], "pmo")
        with patch.object(calendar, "OFFICIAL_TERMS", {}):
            self.assertEqual(get_term(2027, "立春")["source"]["provider"], "hko")

    def test_missing_official_record_requests_consent_before_computing(self):
        with patch.object(calendar, "lunar_at", side_effect=AssertionError("premature estimate")):
            with self.assertRaises(EstimatedTermConsentRequired) as raised:
                get_term(2028, "立春")
        output = raised.exception.to_dict()
        self.assertIsNone(output["evidence"]["time"])
        self.assertEqual(output["status"], "needs_confirmation")
        self.assertFalse(output["evidence"]["usage"]["can_use"])
        self.assertEqual(output["evidence"]["usage"]["confirmations"][0]["status"], "pending")
        json.dumps(output)

    def test_minute_resolution_and_estimate_consent_are_separate(self):
        with self.assertRaises(TermPrecisionConsentRequired):
            get_term(2026, "立冬", require_second_precision=True, allow_estimated_terms=True)
        result = get_term(2026, "立冬", require_second_precision=True, accept_minute_boundaries=True)
        self.assertFalse(result["precision"]["meets_requested_resolution"])
        self.assertIsNone(result["precision"]["accuracy_bound_seconds"])
        self.assertEqual(result["usage"]["confirmations"][0]["status"], "granted")
        self.assertEqual(result["source"]["provider"], "pmo")

    def test_invalid_year_and_unknown_term_are_rejected(self):
        for year in (0, 9999, True, "2026"):
            with self.subTest(year=year), self.assertRaises(ValueError):
                get_term(year, "立春")
        with self.assertRaises(ValueError):
            get_term(2026, "unknown")

    def test_official_query_works_in_a_python_without_site_packages(self):
        root = Path(__file__).resolve().parents[1]
        code = ("import sys; from stg_calendar import get_term; "
                "assert 'lunar_python' not in sys.modules; "
                "assert get_term(2026, '立冬')['source']['provider'] == 'pmo'")
        result = subprocess.run([sys.executable, "-S", "-c", code], cwd=root,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(HAS_CALENDAR, "install the calendar extra")
class CalendarConversion(unittest.TestCase):
    def test_four_pillars_and_local_civil_date(self):
        result = calendar_at("2008-07-21T09:00:00+08:00")
        self.assertEqual(result["pillars"], {"year": "戊子", "month": "己未", "day": "壬戌", "hour": "乙巳"})
        same_instant = calendar_at("2008-07-20T21:00:00-04:00")
        self.assertEqual(same_instant["pillars"]["day"], "辛酉")
        self.assertEqual(same_instant["pillars"]["hour"][-1], "亥")
        self.assertEqual(result["active_term"], same_instant["active_term"])
        self.assertEqual(result["provenance"]["conventions"]["clock"], "local_civil_time")

    def test_day_and_hour_roll_at_local_23(self):
        before = day_hour_pillars(local_clock("2008-07-21T22:59:59+08:00"))
        late = day_hour_pillars(local_clock("2008-07-21T23:00:00+08:00"))
        following = day_hour_pillars(local_clock("2008-07-22T00:30:00+08:00"))
        self.assertNotEqual(before[0], late[0])
        self.assertEqual(late, following)

    def test_published_minute_overrides_a_calculated_second(self):
        before = calendar_at("2025-11-07T12:03:48+08:00")
        after = calendar_at("2025-11-07T12:04:00+08:00")
        self.assertEqual((before["pillars"]["month"], after["pillars"]["month"]), ("丙戌", "丁亥"))
        self.assertEqual(after["active_term"], "立冬")
        self.assertEqual(after["active_term_since"], "2025-11-07T12:04:00+08:00")

    def test_year_and_month_change_together_at_lichun(self):
        before = calendar_at("2023-02-04T10:42:59+08:00")["pillars"]
        after = calendar_at("2023-02-04T10:43:00+08:00")["pillars"]
        self.assertEqual((after["year"], after["month"]), ("癸卯", "甲寅"))
        self.assertNotEqual(before["year"], after["year"])
        self.assertNotEqual(before["month"], after["month"])

    def test_active_term_and_month_boundary_have_separate_evidence(self):
        result = calendar_at("2026-11-23T12:00:00+08:00")["provenance"]
        self.assertEqual(result["active_term"]["name"], "小雪")
        self.assertEqual(result["month_boundary"]["name"], "立冬")

    def test_calculated_terms_remain_estimates_after_consent(self):
        for name in ("小寒", "立春", "冬至"):
            result = get_term(2028, name, allow_estimated_terms=True)
            self.assertEqual(result["name"], name)
            self.assertEqual(datetime.fromisoformat(result["time"]).year, 2028)
            self.assertTrue(result["usage"]["estimated"])
            self.assertEqual(result["usage"]["confirmations"][0]["status"], "granted")
            self.assertIsNone(result["precision"]["accuracy_bound_seconds"])

    def test_dst_ambiguous_and_nonexistent_times_need_an_offset(self):
        for value in ("2026-11-01T01:30:00", "2026-03-08T02:30:00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                local_clock(value, "America/New_York")
        self.assertEqual(local_clock("2026-11-01T01:30:00-04:00").hour, 1)
        with self.assertRaises(ValueError):
            local_clock("2026-11-01T01:30:00-04:00", "America/New_York")
        with self.assertRaises(ValueError):
            local_clock("2026-11-01T12:00:00")

    def test_display_zone_does_not_change_the_instant(self):
        beijing = get_term(2026, "立冬")
        new_york = get_term(2026, "立冬", "America/New_York")
        self.assertEqual(datetime.fromisoformat(beijing["time"]), datetime.fromisoformat(new_york["time"]))
        self.assertTrue(new_york["time"].endswith("-05:00"))


@unittest.skipUnless(HAS_CALENDAR, "install the calendar extra")
class IntervalMatching(unittest.TestCase):
    def report(self, unit, candidate, start, end, **policy):
        left, right = local_clock(start), local_clock(end)
        return resolve_windows_report({"unit": unit, "candidates": [dict(candidate, rule="sample")]},
                                      left, right, left.tzinfo, **policy)

    def test_day_window_respects_23_rollover_and_clipping(self):
        result = self.report("day", {"pillar": "癸亥"}, "2009-09-14T21:30:22+08:00", "2009-09-16T00:00:00+08:00")
        self.assertEqual(result["windows"], [{"pillar": "癸亥", "start": "2009-09-14T23:00:00+08:00",
                                             "end": "2009-09-15T23:00:00+08:00", "rules": ["sample"]}])

    def test_month_window_uses_published_boundary_and_unique_evidence(self):
        result = self.report("month", {"pillar": "丁亥"}, "2025-11-07T12:03:00+08:00",
                             "2025-11-07T12:05:00+08:00", require_second_precision=True,
                             accept_minute_boundaries=True)
        self.assertEqual(result["windows"][0]["start"], "2025-11-07T12:04:00+08:00")
        records = result["provenance"]["term_records"]
        identities = [(r["name"], datetime.fromisoformat(r["time"])) for r in records]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertTrue(all(r["usage"]["can_use"] for r in records))

    def test_crossing_official_coverage_keeps_the_consent_requirement(self):
        args = ("month", {"branch": "丑"}, "2027-12-20T00:00:00+08:00", "2028-01-10T00:00:00+08:00")
        with self.assertRaises(EstimatedTermConsentRequired):
            self.report(*args)
        result = self.report(*args, allow_estimated_terms=True)
        self.assertTrue(result["provenance"]["usage"]["estimated"])
        self.assertEqual({r["source"]["provider"] for r in result["provenance"]["term_records"]}, {"hko", "lunar-python"})

    def test_dst_hour_window_tracks_real_elapsed_time(self):
        zone = ZoneInfo("America/New_York")
        start = local_clock("2026-03-08T00:00:00", zone.key)
        end = local_clock("2026-03-08T05:00:00", zone.key)
        result = resolve_windows_report({"unit": "hour", "candidates": [{"branch": "丑", "rule": "sample"}]},
                                        start, end, zone)
        self.assertEqual((result["windows"][0]["start"], result["windows"][0]["end"]),
                         ("2026-03-08T01:00:00-05:00", "2026-03-08T03:00:00-04:00"))

    def test_empty_candidates_do_not_claim_an_event_is_impossible(self):
        start = local_clock("2026-11-01T12:00:00+08:00")
        result = resolve_windows_report({"unit": "day", "candidates": []}, start, start + timedelta(days=1), start.tzinfo)
        self.assertEqual(result["windows"], [])
        self.assertEqual(result["provenance"]["calendar_dependency"]["uses"], [])
        self.assertTrue(any("不能据此" in text for text in result["provenance"]["usage"]["limitations"]))

    def test_naive_interval_is_rejected_instead_of_using_machine_timezone(self):
        with self.assertRaises(ValueError):
            resolve_windows_report({"unit": "day", "candidates": []}, datetime(2026, 1, 1),
                                   datetime(2026, 1, 2), calendar.BEIJING)


class JsonCLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "stg_calendar", *args],
                              capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    def test_term_and_year_success_are_json(self):
        result = self.run_cli("term", "2026", "立冬")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["source"]["provider"], "pmo")
        result = self.run_cli("year", "2027")
        self.assertEqual(len(json.loads(result.stdout)["terms"]), 24)

    def test_confirmation_is_json_stderr_without_partial_stdout(self):
        for args, code in ((("term", "2028", "立春"), "estimated_term_consent_required"),
                           (("term", "2026", "立冬", "--require-second-precision"), "term_precision_consent_required")):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(json.loads(result.stderr)["error"]["code"], code)

    def test_invalid_input_is_structured(self):
        result = self.run_cli("term", "2026", "unknown")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
