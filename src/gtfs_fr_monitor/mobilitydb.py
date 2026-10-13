"""Links from French feeds to their Mobility Database entries (mobilitydatabase.org).

The Mobility Database catalogue (feeds_v2.csv) names a feed's download URL; for French feeds that
is mostly the data.gouv.fr resource URL. A transport.data.gouv.fr resource is matched by its URL,
its original URL or the resource uuid in a data.gouv.fr URL. When several entries match, an active
one is preferred, then the lowest id.
"""

from __future__ import annotations

import csv
import io
import re

CATALOGUE = "https://files.mobilitydatabase.org/feeds_v2.csv"
FEED_PAGE = "https://mobilitydatabase.org/feeds/gtfs/{id}"
_UUID = re.compile(r"/datasets/r/([0-9a-f-]{36})")
_ID = re.compile(r"[a-z]+-[0-9]+")  # mdb-…, tdg-… (imported from transport.data.gouv.fr), tfs-…


def _order(entry: tuple[str, str]) -> tuple:
    mdb_id, status = entry
    return (status != "active", int(mdb_id.split("-")[1]))


def feed_ids(catalogue_csv: str, datasets: list) -> dict[str, str]:
    """{"<datagouv_id>/<resource id>": "mdb-…"} for the GTFS resources of `datasets` (/api/datasets)."""
    by_url: dict[str, set] = {}
    by_uuid: dict[str, set] = {}
    for row in csv.DictReader(io.StringIO(catalogue_csv)):
        if row.get("data_type") != "gtfs" or row.get("location.country_code") != "FR" or not _ID.fullmatch(row.get("id") or ""):
            continue
        entry = (row["id"], row.get("status") or "")
        for k in ("urls.direct_download", "urls.latest"):
            url = (row.get(k) or "").strip()
            if url:
                by_url.setdefault(url, set()).add(entry)
                m = _UUID.search(url)
                if m:
                    by_uuid.setdefault(m.group(1), set()).add(entry)
    out: dict[str, str] = {}
    for ds in datasets:
        if not isinstance(ds, dict):
            continue
        for res in ds.get("resources") or []:
            if not isinstance(res, dict) or str(res.get("format") or "").upper() != "GTFS":
                continue
            found = set()
            for k in ("url", "original_url"):
                found |= by_url.get(str(res.get(k) or "").strip(), set())
            found |= by_uuid.get(str(res.get("datagouv_id") or ""), set())
            if found and ds.get("datagouv_id") and isinstance(res.get("id"), int):
                out[f"{ds['datagouv_id']}/{res['id']}"] = min(found, key=_order)[0]
    return out
