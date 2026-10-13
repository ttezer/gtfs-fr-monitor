import json
import unittest

from gtfs_fr_monitor.site import LANGS, profile


class SiteProfileTest(unittest.TestCase):
    def test_profile(self):
        p = json.loads(json.dumps(profile(), ensure_ascii=False))  # plain JSON, as export-web reads it
        site = p["site"]
        self.assertEqual((site["langs"], site["default_lang"], site["time_zone"]), (LANGS, "fr", "Europe/Paris"))
        self.assertNotIn("gtfsjp", site["tabs"])
        self.assertEqual(site["regions"]["53"], "Bretagne")
        self.assertTrue(all(set(site["text"][lang]) == set(site["text"]["fr"]) for lang in LANGS))
        self.assertTrue(all("{0}" in site["text"][lang]["updated"] and "{1}" in site["text"][lang]["updated"] for lang in LANGS))
        for k in ("{z}", "{x}", "{y}"):
            self.assertEqual(site["tiles"]["url"].count(k), 1)
        self.assertEqual(sorted(p["atom"]["titles"]), sorted(LANGS))

    def test_head_has_no_analytics(self):
        head = profile()["head"]
        self.assertIn("<title>GTFS-FR Monitor</title>", head)
        self.assertNotIn("googletagmanager", head)
        self.assertEqual(head.count('rel="alternate"'), len(LANGS))


if __name__ == "__main__":
    unittest.main()
