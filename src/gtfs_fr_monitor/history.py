"""Archived files of a resource on transport.data.gouv.fr (docs/DESIGN.md, Anlamlı sürüm).

The platform downloads every resource regularly and keeps each distinct file with a permanent
URL. Two lists describe them: the last 25 entries of a dataset (`history` of /api/datasets/{id},
all formats mixed) and the complete export (/datasets/{numeric id}/resources_history_csv). Both
become Candidates here; entries are untrusted and checked like the gtfs-data.jp records.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from gtfs_fr_pipeline.ids import is_uid
from gtfs_fr_pipeline.source import Rejected

from .tdg import is_history_url

PARIS = ZoneInfo("Europe/Paris")

# Files whose change alone leaves the trips as they are; any other changed file is fingerprinted.
METADATA_FILES = frozenset({"feed_info.txt", "attributions.txt", "translations.txt", "object_codes_extension.txt"})


@dataclass(frozen=True)
class Candidate:
    uid: str
    resource_id: str
    published_at: str  # download time, Europe/Paris, ISO 8601 with offset
    url: str
    files: tuple[tuple[str, str], ...]  # (file name, sha256), sorted
    size: int | None
    stop_times_size: int | None
    start_date: str | None
    end_date: str | None

    def changed_files(self, other: "Candidate") -> set[str]:
        a, b = dict(self.files), dict(other.files)
        return {n for n in a.keys() | b.keys() if a.get(n) != b.get(n)}


def _paris(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(PARIS).isoformat(timespec="seconds")


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _candidate(resource_id: object, payload: object, url: object, org_id: str, feed_id: str,
               rejected: list[Rejected]) -> Candidate | None:
    if not isinstance(payload, dict) or payload.get("format") != "GTFS" or str(resource_id) != feed_id:
        return None  # another resource or format of the dataset
    uid = payload.get("uuid")
    if not is_uid(uid):
        rejected.append(Rejected("INVALID_UID", org_id, feed_id, None, f"uuid={uid!r}"))
        return None
    if not is_history_url(url):
        rejected.append(Rejected("UNTRUSTED_GTFS_URL", org_id, feed_id, uid, "permanent_url not on the history host"))
        return None
    published = _paris(payload.get("download_datetime"))
    if published is None:
        rejected.append(Rejected("INVALID_DATE", org_id, feed_id, uid, "download_datetime"))
        return None
    zmeta = [z for z in payload.get("zip_metadata") or [] if isinstance(z, dict)]
    files = tuple(sorted((str(z.get("file_name")), str(z.get("sha256"))) for z in zmeta))
    if not files:
        rejected.append(Rejected("NO_ZIP_METADATA", org_id, feed_id, uid, "file list missing"))
        return None
    meta = payload.get("resource_metadata") if isinstance(payload.get("resource_metadata"), dict) else {}
    st = next((_int(z.get("uncompressed_size")) for z in zmeta if str(z.get("file_name", "")).endswith("stop_times.txt")), None)
    return Candidate(uid, feed_id, published, url, files, _int(payload.get("filesize")), st,
                     meta.get("start_date") if isinstance(meta.get("start_date"), str) else None,
                     meta.get("end_date") if isinstance(meta.get("end_date"), str) else None)


def _ordered(found: list[Candidate]) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for c in found:
        seen.setdefault(c.uid, c)
    return sorted(seen.values(), key=lambda c: (c.published_at, c.uid))


def from_dataset(detail: dict, org_id: str, feed_id: str) -> tuple[list[Candidate], list[Rejected]]:
    """The recent entries in a dataset's details (oldest first)."""
    rejected: list[Rejected] = []
    found = []
    for e in detail.get("history") or []:
        if isinstance(e, dict):
            payload = e.get("payload")
            c = _candidate(e.get("resource_id"), payload, payload.get("permanent_url") if isinstance(payload, dict) else None,
                           org_id, feed_id, rejected)
            if c:
                found.append(c)
    return _ordered(found), rejected


def from_csv(text: str, org_id: str, feed_id: str) -> tuple[list[Candidate], list[Rejected]]:
    """The complete export (oldest first). Entries from before the platform's 2025 migration have
    no resource_id and are not linked to the resource."""
    csv.field_size_limit(sys.maxsize)
    rejected: list[Rejected] = []
    found = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            payload = json.loads(row.get("payload") or "")
        except json.JSONDecodeError:
            continue
        c = _candidate(row.get("resource_id"), payload, row.get("permanent_url"), org_id, feed_id, rejected)
        if c:
            found.append(c)
    return _ordered(found), rejected


def numeric_dataset_id(detail: dict) -> int | None:
    """The id the CSV export uses, read from the history entries."""
    for e in detail.get("history") or []:
        n = _int((e.get("payload") or {}).get("dataset_id")) if isinstance(e, dict) else None
        if n:
            return n
    return None


def needs_fingerprint(previous: Candidate | None, current: Candidate) -> bool:
    """False when the trips cannot have changed: the same files, or only metadata files changed."""
    if previous is None:
        return True
    changed = previous.changed_files(current)
    return bool(changed - METADATA_FILES)
