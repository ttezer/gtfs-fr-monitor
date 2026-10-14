"""Region of a dataset from the areas it covers (notes/DESIGN.md, Feed kimliği).

transport.data.gouv.fr describes a dataset by its EPCI, communes, départements or region. They are
mapped to one INSEE region code with the official geography API's lists (data/regions.json); a
dataset whose areas lie in several regions, or are not known, has none. The code is the catalog's
`feed_pref_id`, and the region names go to the page's site profile.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REGIONS_FILE = Path(__file__).with_name("data") / "regions.json"
SOURCE = "https://geo.api.gouv.fr"
SCHEMA = "gtfs-fr-monitor-regions/1"


def regions_doc(regions: list[dict], departements: list[dict], epcis: list[dict], retrieved: str) -> dict:
    """The table from the API's /regions, /departements and /epcis?fields=code,codesRegions answers."""
    return {
        "schema": SCHEMA, "source": SOURCE, "retrieved": retrieved,
        "regions": {r["code"]: r["nom"] for r in sorted(regions, key=lambda r: r["code"])},
        "departements": {d["code"]: d["codeRegion"] for d in sorted(departements, key=lambda d: d["code"])},
        "epcis": {e["code"]: sorted(e.get("codesRegions") or []) for e in sorted(epcis, key=lambda e: e["code"])},
    }


@lru_cache(maxsize=1)
def table() -> dict:
    doc = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{REGIONS_FILE}: unexpected schema {doc.get('schema')!r}")
    return doc


def _commune_departement(insee: str) -> str:
    return insee[:3] if insee.startswith("97") else insee[:2]  # overseas: 971..976


def area_regions(area: dict, doc: dict) -> set[str] | None:
    """Region codes of one covered area; None when the area cannot be placed."""
    kind, code = area.get("type"), area.get("insee")
    if not isinstance(code, str) or not code:
        return None
    if kind == "region":
        return {code} if code in doc["regions"] else None
    if kind == "departement":
        r = doc["departements"].get(code)
        return {r} if r else None
    if kind == "commune":
        r = doc["departements"].get(_commune_departement(code))
        return {r} if r else None
    if kind == "epci":
        rs = doc["epcis"].get(code)
        return set(rs) if rs else None
    return None  # pays and anything else


def dataset_region(areas: list, doc: dict | None = None) -> int | None:
    """The INSEE region code (as a number) when every area lies in one and the same region."""
    doc = doc or table()
    found: set[str] = set()
    for area in areas or []:
        if not isinstance(area, dict):
            return None
        rs = area_regions(area, doc)
        if not rs:
            return None
        found |= rs
    return int(found.pop()) if len(found) == 1 and next(iter(found)).isdigit() else None


def region_names(doc: dict | None = None) -> dict[str, str]:
    """{feed_pref_id as text: region name} for the page's site profile."""
    doc = doc or table()
    return {str(int(code)): name for code, name in doc["regions"].items()}
