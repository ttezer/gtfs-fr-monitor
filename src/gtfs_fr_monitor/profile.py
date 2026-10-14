"""The French profile of the shared engine: holiday table and engine configuration (docs/DESIGN.md).

Holidays come from the official calendar API (metropolitan France). Alsace-Moselle (Good Friday,
26 December) and the overseas regions have other days; one national table is used for now.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from gtfs_fr_semantic.holidays import HolidayTable
from gtfs_fr_semantic.reader import Config

HOLIDAYS_FILE = Path(__file__).with_name("data") / "fr_holidays.json"
HOLIDAYS_SOURCE = "https://calendrier.api.gouv.fr/jours-feries/metropole.json"
HOLIDAYS_SCHEMA = "gtfs-jp-semantic-holidays/1"


def holiday_doc(raw: bytes, retrieved: str) -> dict:
    """The engine's holiday table document from the API answer ({"YYYY-MM-DD": name})."""
    days = json.loads(raw.decode("utf-8"))
    if not isinstance(days, dict) or not days or not all(isinstance(k, str) and isinstance(v, str) for k, v in days.items()):
        raise ValueError("unexpected holiday list")
    years = sorted({int(d[:4]) for d in days})
    sha = hashlib.sha256(raw).hexdigest()
    return {"schema": HOLIDAYS_SCHEMA, "version": f"calendrier-metropole-{years[-1]}-{sha[:8]}", "source": HOLIDAYS_SOURCE,
            "source_sha256": sha, "retrieved": retrieved, "first_year": years[0], "last_year": years[-1],
            "holidays": dict(sorted(days.items()))}


def holidays() -> HolidayTable:
    return HolidayTable.load(HOLIDAYS_FILE)


def engine_config() -> Config:
    """The engine's defaults, comparing only dates on or after the new publication: files are
    republished daily and keep, sometimes rewrite, the days already gone."""
    base = Config.load()
    return dataclasses.replace(base, matching=dict(base.matching, compare_from_publication=True))


# Where French stops lie, for the content signature's outside count: metropolitan France with
# Corsica, then Guadeloupe, Martinique, Guyane, La Réunion and Mayotte. Cross-border lines (Geneva,
# Basel, Spain) count their foreign stops as outside.
AREAS = (
    ((41.0, 51.5), (-5.5, 10.0)),
    ((15.8, 16.6), (-61.9, -60.9)),
    ((14.3, 14.95), (-61.3, -60.75)),
    ((2.0, 6.0), (-54.7, -51.5)),
    ((-21.5, -20.8), (55.1, 55.9)),
    ((-13.1, -12.6), (44.9, 45.4)),
)
