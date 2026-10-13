import json
import unittest
from datetime import date

from gtfs_jp_semantic.reader import Config

from gtfs_fr_monitor.profile import engine_config, holiday_doc, holidays


class ProfileTest(unittest.TestCase):
    def test_holidays(self):
        table = holidays()
        self.assertTrue(table.first_year <= 2026 <= table.last_year)
        self.assertEqual([table.category(date(2026, m, d)) for m, d in ((7, 14), (5, 25), (4, 3), (7, 15))],
                         ["hol", "hol", "fri", "wed"])  # Good Friday is a holiday only in Alsace-Moselle

    def test_holiday_doc(self):
        doc = holiday_doc(json.dumps({"2026-07-14": "14 juillet", "2025-01-01": "1er janvier"}).encode(), "2026-10-13")
        self.assertEqual((doc["first_year"], doc["last_year"], list(doc["holidays"])), (2025, 2026, ["2025-01-01", "2026-07-14"]))
        with self.assertRaises(ValueError):
            holiday_doc(b"[]", "2026-10-13")

    def test_engine_config(self):
        cfg, base = engine_config(), Config.load()
        self.assertTrue(cfg.matching["compare_from_publication"])
        self.assertEqual({k: v for k, v in cfg.matching.items() if k != "compare_from_publication"}, base.matching)
        self.assertEqual(Config.from_dict(cfg.as_dict()), cfg)


if __name__ == "__main__":
    unittest.main()
