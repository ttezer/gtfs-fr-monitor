import unittest

from gtfs_fr_monitor.mobilitydb import feed_ids

HEAD = "id,data_type,location.country_code,status,urls.direct_download,urls.latest\n"
UUID = "f8b861f3-6fbd-4eed-a82e-9fed96c9dd09"


def ds(org, *resources):
    return {"datagouv_id": org, "resources": [dict({"format": "GTFS"}, **r) for r in resources]}


class FeedIdsTest(unittest.TestCase):
    def test_matching(self):
        csv = HEAD + (f"mdb-10,gtfs,FR,active,https://www.data.gouv.fr/fr/datasets/r/{UUID},\n"
                      "mdb-11,gtfs,FR,deprecated,https://example.fr/a.zip,\n"
                      "tdg-12,gtfs,FR,active,https://example.fr/a.zip,\n"
                      "mdb-13,gtfs,ES,active,https://example.es/b.zip,\n"
                      "mdb-14,gtfs_rt,FR,active,https://example.fr/rt,\n")
        out = feed_ids(csv, [
            ds("o1", {"id": 1, "datagouv_id": UUID, "url": "https://www.data.gouv.fr/api/1/datasets/r/" + UUID}),  # by uuid
            ds("o2", {"id": 2, "url": "https://example.fr/a.zip"}),  # active preferred
            ds("o3", {"id": 3, "url": "https://example.es/b.zip"}),  # another country
            ds("o4", {"id": 4, "url": "https://example.fr/rt"}),  # not GTFS Schedule
        ])
        self.assertEqual(out, {"o1/1": "mdb-10", "o2/2": "tdg-12"})


if __name__ == "__main__":
    unittest.main()
