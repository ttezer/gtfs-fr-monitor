"""Which archived files are versions (docs/DESIGN.md, Anlamlı sürüm).

A version starts where the trips of the dates ahead change. Each file is compared with the last
file checked before it, not with the last version: a short window (13 days, republished daily)
shares no date with a version from weeks ago, while consecutive files always overlap.

Daily, only the newest file is checked. At the start the history is sampled backwards with a step
that keeps consecutive samples overlapping, within a bounded number of downloads, and the last
`keep` versions are kept. The oldest of them may have started before the first sample.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

from .fingerprint import differs
from .history import Candidate, needs_fingerprint

Fingerprinter = Callable[[Candidate, date], dict[str, str]]


@dataclass(frozen=True)
class SelectionConfig:
    keep: int = 4
    skip_ahead: int = 7
    skip_edge: int = 1
    max_step_days: int = 7
    lookback_days: int = 180
    max_fingerprints: int = 30  # downloads per feed when filling the history


@dataclass(frozen=True)
class Version:
    uid: str
    published_at: str
    url: str
    from_date: str
    to_date: str | None


@dataclass(frozen=True)
class Checked:
    """The last file checked: the next one is compared with it."""

    candidate: Candidate
    fingerprint: dict[str, str] = field(hash=False, compare=False)


def publication_day(c: Candidate) -> date:
    return datetime.fromisoformat(c.published_at).date()


def _version(c: Candidate, fp: dict[str, str]) -> Version:
    return Version(c.uid, c.published_at, c.url, publication_day(c).isoformat(), max(fp) if fp else c.end_date)


def check(versions: list[Version], last: Checked | None, c: Candidate, fingerprint_of: Fingerprinter,
          cfg: SelectionConfig) -> tuple[list[Version], Checked | None]:
    """Compare one file with the last one checked; a changed one starts a version."""
    if last is not None and (c.uid == last.candidate.uid or c.published_at <= last.candidate.published_at):
        return versions, last
    if last is not None and not needs_fingerprint(last.candidate, c):
        return versions, Checked(c, last.fingerprint)  # same trips; later files compare with this one
    day = publication_day(c)
    fp = fingerprint_of(c, day)
    changed = True if last is None else differs(last.fingerprint, fp, day, cfg.skip_ahead, cfg.skip_edge)
    if changed is not False:  # True, or None: a successive timetable
        versions = versions + [_version(c, fp)]
    return versions, Checked(c, fp)


def _step(newest: Candidate, cfg: SelectionConfig) -> int:
    """Half the days the window reaches ahead, so that consecutive samples overlap."""
    ahead = None
    if newest.end_date:
        try:
            ahead = (date.fromisoformat(newest.end_date) - publication_day(newest)).days
        except ValueError:
            ahead = None
    if ahead is None:
        return cfg.max_step_days
    return max(1, min(cfg.max_step_days, ahead // 2))


def samples(candidates: list[Candidate], cfg: SelectionConfig) -> list[Candidate]:
    """Oldest first: the newest file and one file every `step` days before it, within the lookback."""
    if not candidates:
        return []
    newest = candidates[-1]
    step = _step(newest, cfg)
    start = publication_day(newest) - timedelta(days=min(cfg.lookback_days, cfg.max_fingerprints * step))
    picked = [newest]
    for c in reversed(candidates[:-1]):
        day = publication_day(c)
        if day < start or len(picked) >= cfg.max_fingerprints:
            break
        if day <= publication_day(picked[-1]) - timedelta(days=step):
            picked.append(c)
    return list(reversed(picked))


def backfill(candidates: list[Candidate], fingerprint_of: Fingerprinter,
             cfg: SelectionConfig) -> tuple[list[Version], Checked | None]:
    versions: list[Version] = []
    last: Checked | None = None
    for c in samples(candidates, cfg):
        versions, last = check(versions, last, c, fingerprint_of, cfg)
    return versions[-cfg.keep:], last
