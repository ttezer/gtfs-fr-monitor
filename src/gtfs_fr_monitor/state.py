"""Per-feed version state in the data repository: catalog/fr-state/<org>/<feed>.json.

Holds the versions found so far and the reference file with its fingerprint. Written only when
it changes (a new version or a renewed reference), so most daily runs leave it untouched.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from gtfs_fr_pipeline.canonical import write_json_if_changed
from gtfs_fr_pipeline.ids import require_path_id

from .history import Candidate
from .selection import Checked, Version

SCHEMA = "gtfs-fr-monitor-state/1"


def state_path(data_dir: Path, org_id: str, feed_id: str) -> Path:
    return Path(data_dir) / "catalog" / "fr-state" / require_path_id(org_id, "org_id") / f"{require_path_id(feed_id, 'feed_id')}.json"


def load_state(data_dir: Path, org_id: str, feed_id: str) -> tuple[list[Version], Checked | None]:
    path = state_path(data_dir, org_id, feed_id)
    if not path.is_file():
        return [], None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path}: unexpected schema {doc.get('schema')!r}")
    versions = [Version(**v) for v in doc["versions"]]
    ref = doc.get("reference")
    if ref is None:
        return versions, None
    c = dict(ref["candidate"], files=tuple(tuple(f) for f in ref["candidate"]["files"]))
    return versions, Checked(Candidate(**c), dict(ref["fingerprint"]))


def save_state(data_dir: Path, org_id: str, feed_id: str, versions: list[Version], ref: Checked | None) -> bool:
    doc = {
        "schema": SCHEMA,
        "versions": [asdict(v) for v in versions],
        "reference": None if ref is None else {"candidate": asdict(ref.candidate), "fingerprint": ref.fingerprint},
    }
    return write_json_if_changed(state_path(data_dir, org_id, feed_id), doc)
