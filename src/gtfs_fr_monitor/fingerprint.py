"""Service fingerprint of a GTFS ZIP for the dates ahead (notes/DESIGN.md, Anlamlı sürüm).

Daily republished feeds change their file hashes every day (a rolling window, rewritten past
days). What a rider meets is the trips that run on the days ahead, so a version is new only when
that changes. Per date, every running trip is reduced to its line, direction, first and last stop
with times, number of stops and frequencies; the sorted list is hashed. Files are streamed, so a
large stop_times.txt needs memory only for one entry per running trip.
"""

from __future__ import annotations

import collections
import csv
import hashlib
import io
import zipfile
from datetime import date, timedelta
from pathlib import Path

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
HASH_CHARS = 16


class FingerprintError(ValueError):
    """The ZIP lacks what a fingerprint needs."""


def _rows(zf: zipfile.ZipFile, name: str):
    member = next((n for n in zf.namelist() if n.rsplit("/", 1)[-1] == name), None)
    if member is None:
        return
    with zf.open(member) as raw:
        for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")):
            yield {k.strip(): (v or "").strip() for k, v in row.items() if k is not None}


def _yyyymmdd(value: str) -> date | None:
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8])) if len(value) == 8 else None
    except ValueError:
        return None


def _seconds(value: str) -> int | None:
    """GTFS time to seconds after midnight; None when missing (flexible trips) or malformed."""
    parts = value.split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    h, m, s = map(int, parts)
    return h * 3600 + m * 60 + s


def _validity_end(zf: zipfile.ZipFile) -> date | None:
    """The later of feed_info's end date and the last date the calendar files mention: a
    feed_info left from an earlier year must not hide the trips."""
    ends = [_yyyymmdd(r.get("end_date", "")) for r in _rows(zf, "calendar.txt")]
    ends += [_yyyymmdd(r.get("date", "")) for r in _rows(zf, "calendar_dates.txt") if r.get("exception_type") == "1"]
    for row in _rows(zf, "feed_info.txt"):
        ends.append(_yyyymmdd(row.get("feed_end_date", "")))
        break
    ends = [e for e in ends if e]
    return max(ends) if ends else None


def _service_dates(zf: zipfile.ZipFile, first: date, last: date) -> dict[str, set[date]]:
    active: dict[str, set[date]] = collections.defaultdict(set)
    for row in _rows(zf, "calendar.txt"):
        start, end = _yyyymmdd(row.get("start_date", "")), _yyyymmdd(row.get("end_date", ""))
        if not row.get("service_id") or not start or not end:
            continue
        flags = [row.get(w) == "1" for w in WEEKDAYS]
        d = max(start, first)
        while d <= min(end, last):
            if flags[d.weekday()]:
                active[row["service_id"]].add(d)
            d += timedelta(days=1)
    for row in _rows(zf, "calendar_dates.txt"):
        d = _yyyymmdd(row.get("date", ""))
        if not row.get("service_id") or not d or not first <= d <= last:
            continue
        if row.get("exception_type") == "1":
            active[row["service_id"]].add(d)
        elif row.get("exception_type") == "2":
            active[row["service_id"]].discard(d)
    return {sid: ds for sid, ds in active.items() if ds}


def fingerprint(zip_path: Path, after: date, max_days: int = 120) -> dict[str, str]:
    """{ISO date: hash} for every date from `after` to the end of the feed's validity, at most
    `max_days` dates; a date without trips has "". Empty when nothing runs from `after` on."""
    with zipfile.ZipFile(zip_path) as zf:
        end = _validity_end(zf)
        if end is None or end < after:
            return {}
        last = min(after + timedelta(days=max_days - 1), end)
        services = _service_dates(zf, after, last)
        trips: dict[str, tuple[str, str, str]] = {}
        for row in _rows(zf, "trips.txt"):
            if row.get("service_id") in services and row.get("trip_id"):
                trips[row["trip_id"]] = (row.get("route_id", ""), row.get("direction_id", ""), row["service_id"])
        if not trips:
            return {}
        # trip -> [first seq, first stop, first time, last seq, last stop, last time, stops]
        ends: dict[str, list] = {}
        for row in _rows(zf, "stop_times.txt"):
            tid = row.get("trip_id")
            if tid not in trips:
                continue
            try:
                seq = int(row.get("stop_sequence", ""))
            except ValueError:
                raise FingerprintError(f"stop_sequence {row.get('stop_sequence')!r} of trip {tid!r}") from None
            t = _seconds(row.get("departure_time") or row.get("arrival_time") or "")
            e = ends.get(tid)
            if e is None:
                ends[tid] = [seq, row.get("stop_id", ""), t, seq, row.get("stop_id", ""), t, 1]
                continue
            e[6] += 1
            if seq < e[0]:
                e[0:3] = [seq, row.get("stop_id", ""), t]
            if seq > e[3]:
                e[3:6] = [seq, row.get("stop_id", ""), _seconds(row.get("arrival_time") or row.get("departure_time") or "")]
        freq: dict[str, list[tuple]] = collections.defaultdict(list)
        for row in _rows(zf, "frequencies.txt"):
            if row.get("trip_id") in trips:
                freq[row["trip_id"]].append((_seconds(row.get("start_time", "")), _seconds(row.get("end_time", "")),
                                             row.get("headway_secs", ""), row.get("exact_times", "")))

    by_service: dict[str, list[str]] = collections.defaultdict(list)
    for tid, (route, direction, sid) in trips.items():
        e = ends.get(tid)
        sig = (route, direction) + ((e[1], e[2], e[4], e[5], e[6]) if e else ("", None, "", None, 0)) + (tuple(sorted(freq.get(tid, ()), key=repr)),)
        by_service[sid].append(repr(sig))
    for sigs in by_service.values():
        sigs.sort()
    by_date: dict[date, list[str]] = collections.defaultdict(list)
    for sid, ds in services.items():
        if sid in by_service:
            for d in ds:
                by_date[d].extend(by_service[sid])
    if not by_date:
        return {}
    out: dict[str, str] = {}
    d = after
    while d <= last:
        out[d.isoformat()] = (hashlib.sha256("\n".join(sorted(by_date[d])).encode("utf-8")).hexdigest()[:HASH_CHARS]
                              if d in by_date else "")
        d += timedelta(days=1)
    return out


def validity_end(zip_path: Path) -> date | None:
    with zipfile.ZipFile(zip_path) as zf:
        return _validity_end(zf)


def differs(older: dict[str, str], newer: dict[str, str], after: date, skip_ahead: int = 7, skip_edge: int = 1) -> bool | None:
    """Whether the trips differ on a date both fingerprints cover (a date that loses or gains all
    its trips counts). None when the two share no date from `after` on: successive timetables.

    Compared are the shared dates up to `skip_edge` days before either validity end, without the
    first `skip_ahead` of them (at most half, for short windows); when that leaves nothing, the
    two count as the same. Large networks republish short-term adjustments for the next days
    (works, disruptions); a timetable change that starts soon also runs after them and is still
    found. The last date of a window is often incomplete (trips after midnight of the next day).
    Days a rolling window adds after the older validity end are outside the older fingerprint."""
    if not newer:
        return bool(older)  # nothing runs any more
    if not older:
        return None
    shared = sorted(d for d in newer if d >= after.isoformat() and d in older)
    if not shared:
        return None
    last = (min(date.fromisoformat(max(older)), date.fromisoformat(max(newer))) - timedelta(days=skip_edge)).isoformat()
    ahead = [d for d in shared if d <= last]
    return any(older[d] != newer[d] for d in ahead[min(skip_ahead, len(ahead) // 2):])
