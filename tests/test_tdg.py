import json
import unittest

from gtfs_fr_monitor.tdg import TdgClient, is_history_url

ORG = "6703a201386f775e01f4269b"


def resource(rid, title="GTFS", fmt="GTFS", start="2026-10-01", end="2026-12-31"):
    return {"id": rid, "format": fmt, "title": title, "updated": "2026-10-12T06:00:00Z", "is_available": True,
            "metadata": {"start_date": start, "end_date": end}}


def dataset(org=ORG, title="Réseau urbain Exemple", resources=None, kind="public-transit", area=None, licence="lov2"):
    return {"datagouv_id": org, "title": title, "type": kind, "licence": licence,
            "publisher": {"id": "p1", "name": "Ville d'Exemple", "type": "organization"},
            "covered_area": area if area is not None else [{"type": "epci", "nom": "CA Exemple", "insee": "200000000"}],
            "resources": resources if resources is not None else [resource(101)]}


def client(body, calls=None):
    def transport(url, timeout):
        if calls is not None:
            calls.append(url)
        return 200, {}, json.dumps(body).encode("utf-8")
    return TdgClient(transport=transport, sleep=lambda s: None, min_interval=0)


class ListFeedsTest(unittest.TestCase):
    def test_one_feed_per_gtfs_resource(self):
        calls = []
        feeds, rejected = client([
            dataset(),
            dataset(org="aaaaaaaaaaaaaaaaaaaaaaaa", title="Réseau à deux", resources=[resource(201, "Bus"), resource(202, "Car"),
                                                                                   resource(203, fmt="NeTEx")]),
        ], calls).list_feeds()
        self.assertEqual(calls, ["https://transport.data.gouv.fr/api/datasets"])
        self.assertEqual(rejected, [])
        self.assertEqual([(f.org_id, f.feed_id, f.feed_name) for f in feeds], [
            (ORG, "101", "Réseau urbain Exemple"),
            ("aaaaaaaaaaaaaaaaaaaaaaaa", "201", "Réseau à deux — Bus"),
            ("aaaaaaaaaaaaaaaaaaaaaaaa", "202", "Réseau à deux — Car"),
        ])
        f = feeds[0]
        self.assertEqual((f.organization_name, f.license_raw, f.feed_pref_id, f.is_discontinued), ("Ville d'Exemple", "lov2", None, False))
        self.assertEqual((f.latest_feed_start_date, f.latest_feed_end_date), ("2026-10-01", "2026-12-31"))

    def test_scope(self):
        feeds, _ = client([
            dataset(title="Agrégat des réseaux de Bretagne"),
            dataset(kind="vehicles-sharing"),
            dataset(resources=[resource(301, "GTFS RTM"), resource(302, "Référentiel complet (tous les réseaux)")]),
            dataset(resources=[resource(303, fmt="NeTEx")]),
        ]).list_feeds()
        self.assertEqual([f.feed_id for f in feeds], ["301"])
        self.assertEqual(feeds[0].feed_name, "Réseau urbain Exemple")  # one resource left

    def test_invalid_identifiers_are_rejected(self):
        feeds, rejected = client([dataset(org="../x"), dataset(resources=[resource("12/x")])]).list_feeds()
        self.assertEqual(feeds, [])
        self.assertEqual([r.code for r in rejected], ["INVALID_FEED_ID", "INVALID_FEED_ID"])

    def test_region_only_for_a_single_region_area(self):
        one = client([dataset(area=[{"type": "region", "nom": "Bretagne", "insee": "53"}])]).list_feeds()[0][0]
        two = client([dataset(area=[{"type": "region", "insee": "53"}, {"type": "region", "insee": "52"}])]).list_feeds()[0][0]
        self.assertEqual((one.feed_pref_id, two.feed_pref_id), (53, None))


class HistoryUrlTest(unittest.TestCase):
    def test_host(self):
        ok = "https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/52917/52917.20261008.121742.708012.zip"
        self.assertTrue(is_history_url(ok))
        self.assertFalse(is_history_url(ok.replace("https://", "http://")))
        self.assertFalse(is_history_url("https://evil.example.com/52917.zip"))
        self.assertFalse(is_history_url("https://user@transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/x.zip"))


if __name__ == "__main__":
    unittest.main()
