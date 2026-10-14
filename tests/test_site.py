import json
import unittest

from gtfs_fr_monitor.site import LANGS, profile


class SiteProfileTest(unittest.TestCase):
    def test_profile(self):
        p = json.loads(json.dumps(profile({"a/1": "tdg-1"}), ensure_ascii=False))  # plain JSON, as export-web reads it
        site = p["site"]
        self.assertEqual(site["name"], "GTFS-FR Monitor")
        self.assertEqual(site["regions"]["53"], "Bretagne")
        self.assertTrue(all(link["url"].startswith("https://") for link in site["links"]))  # the page shows https only
        self.assertTrue(all("{feed_id}" in link["url"] or "{org_id}" in link["url"] for link in site["feed_links"]))
        self.assertEqual(site["feed_extra"], {"a/1": [{"label": "Mobility Database", "url": "https://mobilitydatabase.org/feeds/gtfs/tdg-1"}]})
        self.assertNotIn("text", site)  # the page template carries this site's texts
        self.assertNotIn("head", p)
        self.assertEqual((p["atom"]["langs"], sorted(p["atom"]["titles"])), (LANGS, sorted(LANGS)))


if __name__ == "__main__":
    unittest.main()
