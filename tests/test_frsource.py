import csv
import io
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from gtfs_jp_monitor.catalog import load_catalog, sync_catalog
from gtfs_jp_monitor.source import FeedRecord

from gtfs_fr_monitor.frsource import FrSource, Settings
from gtfs_fr_monitor.selection import SelectionConfig
from gtfs_fr_monitor.state import load_state

from .schema_support import HAVE_JSONSCHEMA, errors, validator
from .test_fingerprint import write

ORG, FEED, NUMERIC = "6703a201386f775e01f4269b", "82386", 1113
HOST = "https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com"
START = date(2026, 6, 1)


def uid(n):
    return f"{n:08x}-05c2-4d5f-a1d0-fcd33472588c"


class World:
    """transport.data.gouv.fr as seen by the source: archived files, their ZIPs, details and export."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.files = []  # (n, day, zip bytes, stop_times size)
        self.urls = []

    def publish(self, n, day, times=("08:00:00", "08:30:00"), stop_times_size=1000):
        end = (day + timedelta(days=40)).strftime("%Y%m%d")
        path = write(self.tmp / f"{n}.zip", start=(day - timedelta(days=7)).strftime("%Y%m%d"), end=end, times=times)
        self.files.append((n, day, path.read_bytes(), stop_times_size, times))

    def payload(self, n, day, size, times):
        return {"dataset_id": NUMERIC, "uuid": uid(n), "format": "GTFS", "download_datetime": f"{day.isoformat()}T10:00:00Z",
                "permanent_url": f"{HOST}/{FEED}/{FEED}.{n}.zip", "filesize": 1,
                "zip_metadata": [{"file_name": "trips.txt", "sha256": f"t{n}", "uncompressed_size": 10},
                                 {"file_name": "stop_times.txt", "sha256": "".join(times), "uncompressed_size": size}]}

    def detail(self):
        hist = [{"resource_id": int(FEED), "payload": self.payload(n, d, s, t)} for n, d, _, s, t in self.files[-25:]]
        return {"datagouv_id": ORG, "licence": "lov2", "history": list(reversed(hist))}

    def export(self):
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["resource_history_id", "resource_id", "permanent_url", "payload", "inserted_at"])
        for n, d, _, s, t in self.files:
            p = self.payload(n, d, s, t)
            w.writerow([n, FEED, p["permanent_url"], json.dumps(p), p["download_datetime"]])
        return out.getvalue().encode("utf-8")

    def opener(self, url, timeout):
        self.urls.append(url)
        if url == f"https://transport.data.gouv.fr/datasets/{NUMERIC}/resources_history_csv":
            return 200, {}, io.BytesIO(self.export())
        for n, _, data, _, _ in self.files:
            if url == f"{HOST}/{FEED}/{FEED}.{n}.zip":
                return 200, {}, io.BytesIO(data)
        return 404, {}, io.BytesIO(b"")


class FakeClient:
    def __init__(self, world):
        self.world = world

    def list_feeds(self):
        return [FeedRecord(ORG, FEED, "Réseau urbain Exemple", "Ville", None, "lov2", None, False, None, None, None, None, "")], []

    def get_dataset(self, org_id):
        return self.world.detail()


class FrSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.world = World(root)
        self.data = root / "data"
        self.settings = Settings(self.data, root / "work", selection=SelectionConfig(lookback_days=60, max_fingerprints=10))
        for i in range(30):  # daily republication; the timetable changes on day 15
            self.world.publish(i, START + timedelta(days=i), times=("08:00:00", "08:30:00") if i < 15 else ("08:10:00", "08:40:00"))

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, **kw):
        settings = Settings(**{**self.settings.__dict__, **kw})
        return FrSource(settings, client=FakeClient(self.world), opener=self.world.opener)

    def test_first_run_fills_the_history(self):
        src = self.source()
        gens = src.get_generations(ORG, FEED)
        self.assertEqual(gens.rejected, ())
        self.assertEqual(len(gens.generations), 2)
        first, second = gens.generations
        self.assertTrue(15 <= int(second.uid[:8], 16) < 22)  # within one 7-day step of the change
        self.assertEqual((second.rid, second.gtfs_url.startswith(HOST)), (None, True))
        n = int(second.uid[:8], 16)
        self.assertEqual(second.to_date, (START + timedelta(days=n + 40)).isoformat())  # calendar end in the ZIP
        self.assertTrue(second.published_at.endswith("+02:00"))
        self.assertEqual(src.changed_states, [f"{ORG}/{FEED}"])
        self.assertFalse(any((self.settings.work_dir).iterdir()))  # downloads removed

    def test_next_day_same_timetable(self):
        self.source().get_generations(ORG, FEED)
        self.world.publish(30, START + timedelta(days=30), times=("08:10:00", "08:40:00"))
        self.world.urls.clear()
        src = self.source()
        gens = src.get_generations(ORG, FEED)
        self.assertEqual(len(gens.generations), 2)
        self.assertEqual(len(self.world.urls), 1)  # only the newest file
        self.assertEqual(src.changed_states, [])  # reference kept: nothing written

    def test_next_day_new_timetable(self):
        self.source().get_generations(ORG, FEED)
        self.world.publish(30, START + timedelta(days=30), times=("09:00:00", "09:30:00"))
        gens = self.source().get_generations(ORG, FEED)
        self.assertEqual(gens.generations[-1].uid, uid(30))
        self.assertEqual(load_state(self.data, ORG, FEED)[1].candidate.uid, uid(30))

    def test_too_large(self):
        self.world.publish(30, START + timedelta(days=30), stop_times_size=200 * 1024 * 1024)
        gens = self.source().get_generations(ORG, FEED)
        self.assertEqual(([r.code for r in gens.rejected], gens.generations, self.world.urls), (["FEED_TOO_LARGE"], (), []))

    def test_budget(self):
        gens = self.source(download_budget=5).get_generations(ORG, FEED)
        self.assertEqual(([r.code for r in gens.rejected], self.world.urls), (["HISTORY_DEFERRED"], []))

    def test_catalog_sync(self):
        result = sync_catalog(self.source(), self.data)
        self.assertEqual([w["code"] for w in result.warnings], [])
        feeds, gens = load_catalog(self.data)
        self.assertEqual(feeds[(ORG, FEED)]["license"], {"raw": "lov2", "id": "etalab-2.0"})
        self.assertEqual(len(gens[(ORG, FEED)]), 2)
        if not HAVE_JSONSCHEMA:
            return
        doc = {"schema": "gtfs-jp-monitor-catalog-generations/1", "generations": list(gens[(ORG, FEED)].values())}
        self.assertEqual(errors(validator("catalog-generations.schema.json"), doc), [])


if __name__ == "__main__":
    unittest.main()
