"""Synthetic update fixtures test import mechanics, not unpublished official values."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from solar_term_calendar import pmo_terms, update_terms
from solar_term_calendar.hko_terms import HKO_TERMS


def synthetic_document():
    # Reuse public HKO values only as a schema fixture. Never install this as PMO data.
    return {"publication": "SYNTHETIC TEST FIXTURE - NOT A PMO PUBLICATION",
            "source_url": "https://pmo.cas.cn/synthetic-test-only",
            "terms": {name: moment.isoformat(timespec="minutes")
                      for (year, name), moment in HKO_TERMS.items() if year == 2027}}


class AnnualUpdates(unittest.TestCase):
    def test_preview_is_read_only_and_apply_requires_complete_data(self):
        document = synthetic_document()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "updates.json"
            with patch.object(update_terms, "UPDATE_FILE", path), patch.object(pmo_terms, "UPDATE_FILE", path):
                preview = update_terms.preview_update(2027, document)
                self.assertEqual(len(preview), 24)
                self.assertFalse(path.exists())
                update_terms.apply_update(2027, document)
                self.assertEqual(pmo_terms.load_updates(), {"2027": document})
                before = path.read_bytes()
                del document["terms"]["惊蛰"]
                with self.assertRaises(ValueError):
                    update_terms.apply_update(2027, document)
                self.assertEqual(path.read_bytes(), before)

    def test_wrong_host_month_spacing_and_resolution_are_rejected(self):
        cases = (("source_url", "https://pmo.cas.cn.example.com/fake"),
                 ("source_url", "http://pmo.cas.cn/fake"), ("publication", ""),
                 ("立春", "2027-03-04T09:46+08:00"),
                 ("大寒", "2027-01-06T15:30+08:00"),
                 ("立春", "2027-02-04T09:46:12+08:00"))
        for key, value in cases:
            document = copy.deepcopy(synthetic_document())
            (document["terms"] if key in pmo_terms.TERM_MONTH else document)[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                pmo_terms.parse_annual_update(2027, document)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "重复"):
            json.loads('{"terms": {"立春": "a", "立春": "b"}}', object_pairs_hook=pmo_terms.unique_keys)

    def test_external_update_is_loaded_with_edition_and_new_fingerprint(self):
        from solar_term_calendar.calendar import TERM_DATA_VERSION
        with TemporaryDirectory() as directory:
            path = Path(directory) / "updates.json"
            path.write_text(json.dumps({"2027": synthetic_document()}), encoding="utf-8")
            code = ("import json; from solar_term_calendar import get_term; "
                    "print(json.dumps(get_term(2027, '惊蛰')))")
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                    encoding="utf-8", env={**os.environ, "SOLAR_TERM_CALENDAR_UPDATES": str(path)})
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["source"]["provider"], "pmo")
            self.assertEqual(output["source"]["publication"]["kind"], "reviewed_annual_update")
            self.assertIn("SYNTHETIC", output["source"]["publication"]["title"])
            self.assertNotEqual(output["source"]["data_version"], TERM_DATA_VERSION)

    def test_update_cli_defaults_to_preview(self):
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.json", Path(directory) / "updates.json"
            source.write_text(json.dumps(synthetic_document()), encoding="utf-8")
            base = [sys.executable, "-m", "solar_term_calendar.update_terms", "2027", str(source)]
            env = {**os.environ, "SOLAR_TERM_CALENDAR_UPDATES": str(output)}
            preview = subprocess.run(base, env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertFalse(json.loads(preview.stdout)["applied"])
            self.assertFalse(output.exists())
            applied = subprocess.run([*base, "--apply"], env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertTrue(json.loads(applied.stdout)["applied"])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"2027": synthetic_document()})


if __name__ == "__main__":
    unittest.main()
