import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from gtfs_fr_monitor.fingerprint import differs, fingerprint

CAL = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
TODAY = date(2026, 10, 13)  # a Tuesday


def write(path: Path, start="20261006", end="20261130", times=("08:00:00", "08:30:00"), dates="", freq="", feed_end=None):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("calendar.txt", CAL + f"W,1,1,1,1,1,1,1,{start},{end}\n")
        if dates:
            zf.writestr("calendar_dates.txt", "service_id,date,exception_type\n" + dates)
        zf.writestr("trips.txt", "route_id,service_id,trip_id,direction_id\nR1,W,T1,0\nR1,W,T2,1\n")
        zf.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                    f"T1,{times[0]},{times[0]},A,1\nT1,{times[1]},{times[1]},B,2\n"
                    "T2,09:00:00,09:00:00,B,1\nT2,09:30:00,09:30:00,A,2\n")
        if freq:
            zf.writestr("frequencies.txt", "trip_id,start_time,end_time,headway_secs\n" + freq)
        if feed_end:
            zf.writestr("feed_info.txt", f"feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\np,https://x.fr,fr,{start},{feed_end}\n")
    return path


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.base = fingerprint(write(self.dir / "base.zip"), TODAY)

    def tearDown(self):
        self.tmp.cleanup()

    def fp(self, name, **kw):
        return fingerprint(write(self.dir / name, **kw), TODAY)

    def test_dates_ahead_only(self):
        self.assertEqual(min(self.base), "2026-10-13")
        self.assertEqual(max(self.base), "2026-11-30")
        self.assertEqual(len(set(self.base.values())), 1)  # every day the same trips

    def test_rolling_window_is_no_change(self):
        later = self.fp("later.zip", start="20261007", end="20261201")
        self.assertFalse(differs(self.base, later, TODAY))

    def test_rewritten_past_day_is_no_change(self):
        past = self.fp("past.zip", dates="W,20261012,2\n")
        self.assertFalse(differs(self.base, past, TODAY))

    def test_retimed_trip(self):
        self.assertTrue(differs(self.base, self.fp("retimed.zip", times=("08:05:00", "08:35:00")), TODAY))

    def test_day_without_trips(self):
        self.assertTrue(differs(self.base, self.fp("holiday.zip", dates="W,20261111,2\n"), TODAY))

    def test_short_term_adjustment_is_no_change(self):
        # Within the next 7 days only: works or a disruption, not a new timetable.
        self.assertFalse(differs(self.base, self.fp("strike.zip", dates="W,20261015,2\n"), TODAY))
        self.assertTrue(differs(self.base, self.fp("strike.zip", dates="W,20261015,2\n"), TODAY, skip_ahead=0))

    def test_short_window_skips_at_most_half(self):
        # 13-day window published daily: 6 days ahead, the first 3 are skipped (the last is the window edge).
        short = lambda name, dates="": self.fp(name, end="20261018", dates=dates)
        base = short("s0.zip")
        self.assertFalse(differs(base, short("s1.zip", "W,20261014,2\n"), TODAY))
        self.assertTrue(differs(base, short("s2.zip", "W,20261016,2\n"), TODAY))

    def test_last_days_cut_within_the_same_validity(self):
        cut = self.fp("cut.zip", end="20261125", feed_end="20261130")
        self.assertEqual(cut["2026-11-28"], "")
        base = fingerprint(write(self.dir / "b2.zip", feed_end="20261130"), TODAY)
        self.assertTrue(differs(base, cut, TODAY))

    def test_frequencies(self):
        a = self.fp("fa.zip", freq="T1,06:00:00,09:00:00,600\n")
        b = self.fp("fb.zip", freq="T1,06:00:00,09:00:00,900\n")
        self.assertTrue(differs(a, b, TODAY))

    def test_last_day_of_a_window_is_not_compared(self):
        edge = self.fp("edge.zip", dates="W,20261130,2\n", end="20261130")
        later = self.fp("later.zip", start="20261007", end="20261201")
        self.assertFalse(differs(edge, later, TODAY))

    def test_no_common_dates(self):
        nxt = fingerprint(write(self.dir / "next.zip", start="20261201", end="20261231"), date(2026, 12, 1))
        self.assertIsNone(differs(self.base, nxt, date(2026, 12, 1)))

    def test_nothing_ahead(self):
        ended = fingerprint(write(self.dir / "old.zip", end="20261010"), TODAY)
        self.assertEqual(ended, {})
        self.assertTrue(differs(self.base, ended, TODAY))  # service stops
        self.assertFalse(differs({}, ended, TODAY))


if __name__ == "__main__":
    unittest.main()
