import unittest
from datetime import date, timedelta

from gtfs_fr_monitor.history import Candidate
from gtfs_fr_monitor.selection import SelectionConfig, backfill, check, samples

START = date(2026, 6, 1)
CFG = SelectionConfig()


def uid(n):
    return f"{n:08x}-0000-4000-8000-000000000000"


def cand(n, day, files=None, end=None):
    """File n downloaded on `day` (Paris noon)."""
    files = files or (("stops.txt", "s"), ("trips.txt", f"t{n}"))
    return Candidate(uid(n), "1", f"{day.isoformat()}T12:00:00+02:00", f"https://h/{n}.zip", files, 1, 1,
                     day.isoformat(), end)


def timetable(label, window=(0, 60)):
    """A fingerprint maker: the same `label` trips on every date of a rolling window around the day."""
    def fp(day):
        return {(day + timedelta(days=i)).isoformat(): label for i in range(window[0], window[1])}
    return fp


class Recorder:
    """fingerprint_of for tests: the timetable in force for each file, and the files downloaded."""

    def __init__(self, plan):
        self.plan = plan  # uid -> (day -> fingerprint)
        self.calls = []

    def __call__(self, c, day):
        self.calls.append(c.uid)
        return self.plan[c.uid](day)


class CheckTest(unittest.TestCase):
    def test_daily_republication_is_one_version(self):
        files = [cand(i, START + timedelta(days=i)) for i in range(10)]
        rec = Recorder({c.uid: timetable("A") for c in files})
        versions, last = [], None
        for c in files:
            versions, last = check(versions, last, c, rec, CFG)
        self.assertEqual([v.uid for v in versions], [uid(0)])
        self.assertEqual(versions[0].from_date, "2026-06-01")
        self.assertEqual(last.candidate.uid, uid(9))

    def test_change_starts_a_version(self):
        files = [cand(i, START + timedelta(days=i)) for i in range(6)]
        rec = Recorder({c.uid: timetable("A" if i < 3 else "B") for i, c in enumerate(files)})
        versions, last = [], None
        for c in files:
            versions, last = check(versions, last, c, rec, CFG)
        self.assertEqual([v.uid for v in versions], [uid(0), uid(3)])

    def test_metadata_only_change_is_not_downloaded(self):
        a = cand(1, START, files=(("feed_info.txt", "x"), ("trips.txt", "t")))
        b = cand(2, START + timedelta(days=1), files=(("feed_info.txt", "y"), ("trips.txt", "t")))
        rec = Recorder({a.uid: timetable("A"), b.uid: timetable("B")})
        versions, last = check([], None, a, rec, CFG)
        versions, last = check(versions, last, b, rec, CFG)
        self.assertEqual((rec.calls, [v.uid for v in versions], last.candidate.uid), ([uid(1)], [uid(1)], uid(2)))

    def test_successive_timetables(self):
        # The old file ends before the new one's dates: no shared date, still a new version.
        a, b = cand(1, START), cand(2, START + timedelta(days=30))
        rec = Recorder({a.uid: timetable("A", (0, 20)), b.uid: timetable("A", (0, 20))})
        versions, last = check([], None, a, rec, CFG)
        versions, last = check(versions, last, b, rec, CFG)
        self.assertEqual([v.uid for v in versions], [uid(1), uid(2)])

    def test_older_or_same_file_is_ignored(self):
        a, b = cand(2, START + timedelta(days=1)), cand(1, START)
        rec = Recorder({a.uid: timetable("A"), b.uid: timetable("B")})
        versions, last = check([], None, a, rec, CFG)
        self.assertEqual(check(versions, last, b, rec, CFG), (versions, last))
        self.assertEqual(check(versions, last, a, rec, CFG), (versions, last))


class BackfillTest(unittest.TestCase):
    def test_samples_overlap_short_windows(self):
        # A 13-day window republished daily (6 days ahead): step 3, at most 30 samples.
        files = [cand(i, START + timedelta(days=i), end=(START + timedelta(days=i + 6)).isoformat()) for i in range(200)]
        picked = samples(files, CFG)
        self.assertEqual(picked[-1].uid, uid(199))
        self.assertEqual(len(picked), 30)
        days = [int(c.uid[:8], 16) for c in picked]
        self.assertEqual({b - a for a, b in zip(days, days[1:])}, {3})

    def test_keeps_the_last_versions(self):
        # A daily feed with a new timetable every 20 days for 200 days; 7-day steps, lookback 180 days.
        files = [cand(i, START + timedelta(days=i)) for i in range(200)]
        rec = Recorder({c.uid: timetable(f"T{i // 20}") for i, c in enumerate(files)})
        versions, last = backfill(files, rec, CFG)
        self.assertEqual(len(rec.calls), 26)  # 180 days / 7 + the newest
        self.assertEqual(len(versions), 4)
        starts = [int(v.uid[:8], 16) for v in versions]
        # Each version starts at the first sample on or after the change (within one step).
        self.assertEqual([s // 20 for s in starts], [6, 7, 8, 9])
        self.assertTrue(all(0 <= s % 20 < 7 for s in starts))
        self.assertEqual(last.candidate.uid, uid(199))

    def test_empty(self):
        self.assertEqual(backfill([], Recorder({}), CFG), ([], None))


if __name__ == "__main__":
    unittest.main()
