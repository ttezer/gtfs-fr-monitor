"""The site profile for the page and Atom feeds (docs/data-model.md §10.4), passed to
`python -m gtfs_fr_pipeline export-web --site-profile`.

The page template (web/prototype/index.html) already carries this site's languages, texts, look,
tiles and tabs; the profile adds what comes from data: region names and links.
"""

from __future__ import annotations

from .mobilitydb import FEED_PAGE
from .regions import region_names

NAME = "GTFS-FR Monitor"
LANGS = ["fr", "en", "tr"]
ANALYZER = "https://ttezer.github.io/gtfs-analyzer/"

LINKS = [
    {"label": "GTFS Analyzer", "url": ANALYZER},
    {"label": "transport.data.gouv.fr", "url": "https://transport.data.gouv.fr/datasets?type=public-transit"},
    {"label": "Mobility Database (MobilityData)", "url": "https://mobilitydatabase.org/feeds?gtfs=true"},
    {"label": "GTFS (MobilityData)", "url": "https://gtfs.org/documentation/schedule/reference/"},
    {"label": "Plan IGN", "url": "https://geoservices.ign.fr/services-geoplateforme-diffusion"},
    {"label": "calendrier.api.gouv.fr", "url": "https://calendrier.api.gouv.fr/"},
    {"label": "geo.api.gouv.fr", "url": "https://geo.api.gouv.fr/"},
    {"label": "gtfs-fr-monitor", "url": "https://github.com/ttezer/gtfs-fr-monitor"},
]
# {org_id} is the dataset's datagouv_id, {feed_id} the resource id (tdg.py).
FEED_LINKS = [
    {"label": "transport.data.gouv.fr", "url": "https://transport.data.gouv.fr/resources/{feed_id}"},
    {"label": "Dataset", "url": "https://transport.data.gouv.fr/datasets/{org_id}"},
]

ATOM_TITLES = {"fr": f"{NAME} · changements majeurs", "en": f"{NAME} · major changes", "tr": f"{NAME} · önemli değişiklikler"}


def profile(mdb: dict[str, str] | None = None) -> dict:
    """mdb: {"org/feed": "mdb-…"} (mobilitydb.feed_ids) for links to the Mobility Database."""
    extra = {k: [{"label": "Mobility Database", "url": FEED_PAGE.format(id=v)}] for k, v in sorted((mdb or {}).items())}
    return {
        "site": {
            # Languages, time zone, tiles, tabs and texts are the page's own defaults; these come from data.
            "name": NAME, "regions": region_names(), "links": LINKS, "feed_links": FEED_LINKS, "feed_extra": extra,
        },
        "atom": {"langs": LANGS, "titles": ATOM_TITLES, "author": NAME, "tag": "gtfs-fr-monitor"},
    }
