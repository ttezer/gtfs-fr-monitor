import csv
import io
import json
import unittest

from gtfs_fr_monitor.history import from_csv, from_dataset, needs_fingerprint, numeric_dataset_id

ORG, FEED = "6703a201386f775e01f4269b", "82386"
HOST = "https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com"


def uid(n):
    return f"{n:08x}-05c2-4d5f-a1d0-fcd33472588c"


def payload(n, when, files=None, fmt="GTFS", url=None):
    files = {"stops.txt": "s1", "trips.txt": f"t{n}"} if files is None else files
    return {"dataset_id": 1113, "uuid": uid(n), "format": fmt, "download_datetime": when, "filesize": 1000 + n,
            "permanent_url": url or f"{HOST}/{FEED}/{FEED}.{n}.zip",
            "zip_metadata": [{"file_name": k, "sha256": v, "uncompressed_size": 10 * n} for k, v in files.items()],
            "resource_metadata": {"start_date": "2026-10-12", "end_date": "2026-12-12"}}


def entry(n, when, resource=82386, **kw):
    return {"resource_id": resource, "payload": payload(n, when, **kw)}


class FromDatasetTest(unittest.TestCase):
    def test_entries_of_the_resource_oldest_first(self):
        detail = {"history": [
            entry(3, "2026-10-13T06:21:56.844624Z"),
            entry(1, "2026-10-11T22:00:00Z"),
            entry(2, "2026-10-12T18:16:04Z"),
            entry(9, "2026-10-12T00:00:00Z", resource=99999),  # another resource
            entry(8, "2026-10-12T00:00:00Z", fmt="NeTEx"),
            entry(2, "2026-10-12T18:16:04Z"),  # repeated
        ]}
        found, rejected = from_dataset(detail, ORG, FEED)
        self.assertEqual(rejected, [])
        self.assertEqual([c.uid for c in found], [uid(1), uid(2), uid(3)])
        self.assertEqual(found[0].published_at, "2026-10-12T00:00:00+02:00")  # Paris time: the date moves
        self.assertEqual(found[2].published_at, "2026-10-13T08:21:56+02:00")
        self.assertEqual((found[2].size, found[2].stop_times_size, found[2].start_date), (1003, None, "2026-10-12"))
        self.assertEqual(numeric_dataset_id(detail), 1113)

    def test_untrusted_entries_are_rejected(self):
        bad_uid = entry(1, "2026-10-12T00:00:00Z")
        bad_uid["payload"]["uuid"] = "../x"
        found, rejected = from_dataset({"history": [
            bad_uid,
            entry(2, "2026-10-12T00:00:00Z", url="https://evil.example.com/x.zip"),
            entry(3, "not a date"),
            entry(4, "2026-10-12T00:00:00Z", files={}),
        ]}, ORG, FEED)
        self.assertEqual(found, [])
        self.assertEqual([r.code for r in rejected], ["INVALID_UID", "UNTRUSTED_GTFS_URL", "INVALID_DATE", "NO_ZIP_METADATA"])


class FromCsvTest(unittest.TestCase):
    def test_export(self):
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["resource_history_id", "resource_id", "permanent_url", "payload", "inserted_at"])
        for n, res in ((1, ""), (2, FEED), (3, FEED)):  # the first predates the 2025 migration: no resource_id
            p = payload(n, f"2026-10-1{n}T10:00:00Z")
            w.writerow([n, res, p["permanent_url"], json.dumps(p), p["download_datetime"]])
        found, rejected = from_csv(out.getvalue(), ORG, FEED)
        self.assertEqual(([c.uid for c in found], rejected), ([uid(2), uid(3)], []))


class NeedsFingerprintTest(unittest.TestCase):
    def test_prefilter(self):
        def cand(n, files):
            return from_dataset({"history": [entry(n, "2026-10-12T00:00:00Z", files=files)]}, ORG, FEED)[0][0]
        base = cand(1, {"stops.txt": "a", "trips.txt": "b", "feed_info.txt": "c"})
        self.assertTrue(needs_fingerprint(None, base))
        self.assertFalse(needs_fingerprint(base, cand(2, {"stops.txt": "a", "trips.txt": "b", "feed_info.txt": "c"})))
        self.assertFalse(needs_fingerprint(base, cand(3, {"stops.txt": "a", "trips.txt": "b", "feed_info.txt": "x"})))
        self.assertTrue(needs_fingerprint(base, cand(4, {"stops.txt": "a", "trips.txt": "b", "feed_info.txt": "c", "calendar_dates.txt": "d"})))
        self.assertTrue(needs_fingerprint(base, cand(5, {"stops.txt": "a", "trips.txt": "x", "feed_info.txt": "c"})))


if __name__ == "__main__":
    unittest.main()
