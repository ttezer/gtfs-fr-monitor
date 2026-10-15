"""The French CatalogSource: feeds from transport.data.gouv.fr, versions from their archived files.

get_generations returns the versions of a feed (notes/DESIGN.md, Anlamlı sürüm). The first time a
feed is seen, its history export is sampled; afterwards only the newest archived file is checked.
Files are downloaded to `work_dir` for the fingerprint and removed at once. Downloads per run are
bounded; a feed left without its history when the budget runs out gets it on a later run.
"""

from __future__ import annotations

import csv
import functools
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from gtfs_fr_pipeline.download import DownloadError, download_zip, urllib_opener
from gtfs_fr_pipeline.ids import is_path_id
from gtfs_fr_pipeline.source import ApiError, FeedGenerations, GenerationRecord, Rejected

from .fingerprint import FingerprintError, fingerprint, validity_end
from .history import Candidate, from_csv, from_dataset, numeric_dataset_id
from .selection import SelectionConfig, backfill, check
from .state import load_state, save_state
from .tdg import BASE_URL, USER_AGENT, TdgClient, is_history_url

MB = 1024 * 1024
UNREADABLE = (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, NotImplementedError, csv.Error,
              FingerprintError, OSError, ValueError, KeyError)


@dataclass
class Settings:
    data_dir: Path
    work_dir: Path
    max_stop_times_bytes: int = 100 * MB  # larger feeds wait for a streaming engine (notes/FEASIBILITY.md)
    max_zip_bytes: int = 512 * MB
    max_csv_bytes: int = 64 * MB
    fingerprint_days: int = 120
    download_budget: int = 300  # per run
    max_seconds: float | None = None  # per run: no download starts after it, so the run reaches its commit
    selection: SelectionConfig = field(default_factory=SelectionConfig)


def _is_export_url(url: object) -> bool:
    return isinstance(url, str) and url.startswith(f"{BASE_URL}/datasets/") and url.endswith("/resources_history_csv")


class FrSource:
    def __init__(self, settings: Settings, client: TdgClient | None = None, opener=None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.settings = settings
        self.client = client or TdgClient()
        self._opener = opener or functools.partial(urllib_opener, user_agent=USER_AGENT)
        self._clock = clock
        self._deadline = None if settings.max_seconds is None else clock() + settings.max_seconds
        self.downloads = 0
        self.unreadable: list[str] = []  # archived files that are no readable GTFS ZIP
        self.changed_states: list[str] = []

    def out_of_time(self) -> bool:
        return self._deadline is not None and self._clock() >= self._deadline

    def list_feeds(self):
        return self.client.list_feeds()

    # --- downloads ---

    def _fetch(self, url: str, name: str, max_bytes: int, allowed) -> Path:
        if self.downloads >= self.settings.download_budget or self.out_of_time():
            raise _BudgetSpent()
        self.downloads += 1
        try:
            return download_zip(url, self.settings.work_dir / name, max_bytes=max_bytes, opener=self._opener, allowed=allowed).path
        except DownloadError as err:
            raise ApiError(f"download failed: {err.code}") from None

    def _fingerprint(self, c: Candidate, day: date) -> tuple[dict[str, str], str | None]:
        path = self._fetch(c.url, "candidate.zip", self.settings.max_zip_bytes, is_history_url)
        try:
            end = validity_end(path)
            return fingerprint(path, day, self.settings.fingerprint_days), end.isoformat() if end else None
        except UNREADABLE:
            # Not a readable GTFS ZIP (some archived files are not zips at all): no timetable, like an
            # expired file. Failing the feed instead would stop it on the same file every night.
            self.unreadable.append(c.uid)
            return {}, None
        finally:
            path.unlink(missing_ok=True)

    def _history_csv(self, numeric_id: int) -> str:
        url = f"{BASE_URL}/datasets/{numeric_id}/resources_history_csv"
        path = self._fetch(url, "history.csv", self.settings.max_csv_bytes, _is_export_url)
        try:
            return path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

    # --- CatalogSource ---

    def get_generations(self, org_id: str, feed_id: str) -> FeedGenerations:
        if not (is_path_id(org_id) and is_path_id(feed_id)):
            raise ApiError(f"invalid feed path {org_id!r}/{feed_id!r}")
        detail = self.client.get_dataset(org_id)
        recent, rejected = from_dataset(detail, org_id, feed_id)
        versions, ref = load_state(self.settings.data_dir, org_id, feed_id)
        notes: list[Rejected] = list(rejected)
        newest = recent[-1] if recent else None
        if newest and (newest.stop_times_size or 0) >= self.settings.max_stop_times_bytes:
            notes.append(Rejected("FEED_TOO_LARGE", org_id, feed_id, newest.uid, f"stop_times.txt {newest.stop_times_size} bytes"))
        else:
            try:
                if ref is None:
                    if self.settings.download_budget - self.downloads < self.settings.selection.max_fingerprints + 1 or self.out_of_time():
                        raise _BudgetSpent()  # do not start a history that cannot be finished
                    numeric = numeric_dataset_id(detail)
                    if numeric is None:
                        raise ApiError("dataset id for the history export not found")
                    found, more = from_csv(self._history_csv(numeric), org_id, feed_id)
                    notes.extend(more)
                    versions, ref = backfill(found or recent, self._fingerprint, self.settings.selection)
                elif newest is not None:
                    versions, ref = check(versions, ref, newest, self._fingerprint, self.settings.selection)
            except _BudgetSpent:
                notes.append(Rejected("HISTORY_DEFERRED", org_id, feed_id, None, "download or time budget of this run spent"))
            if save_state(self.settings.data_dir, org_id, feed_id, versions, ref):
                self.changed_states.append(f"{org_id}/{feed_id}")
        return FeedGenerations(
            org_id=org_id, feed_id=feed_id, license_raw=str(detail.get("licence") or ""),
            reported_max_prev=None, reported_max_next=None,
            generations=tuple(GenerationRecord(v.uid, None, v.url, v.from_date, v.to_date, v.published_at, "") for v in versions),
            rejected=tuple(notes),
        )


class _BudgetSpent(Exception):
    pass
