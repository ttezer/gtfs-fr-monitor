"""The French site's profile for gtfs-jp-monitor's page and Atom feeds (its data-model §10.4).

Passed to `export-web --site-profile`. Texts are JSON strings; "{0}", "{1}" stand for the
arguments of the page's own text with the same key.
"""

from __future__ import annotations

from html import escape

from .mobilitydb import FEED_PAGE
from .regions import region_names

NAME = "GTFS-FR Monitor"
SITE_URL = "https://ttezer.github.io/gtfs-fr-monitor/"
LANGS = ["fr", "en", "tr"]
ANALYZER = "https://ttezer.github.io/gtfs-analyzer/"
_A = f'<a href="{ANALYZER}" target="_blank" rel="noopener">GTFS Analyzer</a>'

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

TILES = {
    # Plan IGN v2 from the Géoplateforme (Licence Ouverte), the French counterpart of the GSI tiles.
    "url": "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2"
           "&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
    "label": "Plan IGN",
    "link": "https://geoservices.ign.fr/services-geoplateforme-diffusion",
}

TEXT = {
    "fr": {
        "coordWarn": "{0} : {1} arrêts hors du territoire français et {2} aux latitude et longitude apparemment inversées ; "
                     "leurs lignes peuvent s'afficher mal sur les cartes et dans les comparaisons d'itinéraires.",
        "tagline": "Qualité, préparation à la publication et historique des changements des flux de transport.data.gouv.fr",
        "prefecture": "Région",
        "updated": "Dernière mise à jour il y a {0} ({1}, heure de Paris).",
        "notice": "<b>Aperçu.</b> {0} flux, {1} publications, analysés avec " + _A + " {2}. Une publication est retenue quand les courses des jours à venir changent ; "
                  "les republications quotidiennes sans changement d'horaire ne comptent pas. Les plus grands flux "
                  "(stop_times.txt de 100 Mo ou plus) ne sont pas encore suivis.",
        "footer": "Données : transport.data.gouv.fr et les producteurs. Les scores et rapports de changements sont dérivés de ces données ; "
                  "la licence de chaque flux figure dans son panneau (Licence Ouverte, ODbL…). Les noms de flux et d'arrêts sont affichés "
                  "tels que publiés. Carte : Plan IGN (IGN-F / Géoplateforme). Jours fériés : calendrier.api.gouv.fr (métropole). "
                  "Aucune mesure d'audience.",
    },
    "en": {
        "coordWarn": "The {0}: {1} stops outside French territory and {2} with latitude and longitude apparently swapped; "
                     "their lines may look wrong on maps and in route comparisons.",
        "tagline": "Feed quality, publication readiness and change history for transport.data.gouv.fr feeds",
        "prefecture": "Region",
        "updated": "Last updated {0} ago ({1} Paris time).",
        "notice": "<b>Preview.</b> {0} feeds, {1} publications, analysed with " + _A + " {2}. A publication counts when the trips of the days ahead change; "
                  "daily republications without a timetable change do not. The largest feeds (stop_times.txt of 100 MB or more) "
                  "are not monitored yet.",
        "footer": "Data: transport.data.gouv.fr and the data producers. Scores and change reports are derived from these data; each feed's "
                  "licence is shown in its panel (Licence Ouverte, ODbL…). Feed and stop names are shown as published. Map: Plan IGN "
                  "(IGN-F / Géoplateforme). Public holidays: calendrier.api.gouv.fr (metropolitan France). No visitor analytics.",
    },
    "tr": {
        "coordWarn": "{0}: {1} durak Fransa topraklarının dışında, {2} durakta enlem ve boylam yer değiştirmiş görünüyor; "
                     "bu durakların hatları haritada ve güzergâh karşılaştırmasında yanlış görünebilir.",
        "tagline": "transport.data.gouv.fr feed'lerinin kalitesi, yayına hazırlığı ve değişiklik geçmişi",
        "prefecture": "Bölge",
        "updated": "Son güncelleme {0} önce ({1}, Paris saati).",
        "notice": "<b>Önizleme.</b> {0} feed, {1} yayın; " + _A + " {2} ile analiz edildi. Bir yayın, önümüzdeki günlerin seferleri değiştiğinde sayılır; "
                  "tarifesi değişmeyen günlük yeniden yayınlar sayılmaz. En büyük feed'ler (stop_times.txt 100 MB ve üstü) "
                  "henüz izlenmiyor.",
        "footer": "Veri kaynağı: transport.data.gouv.fr ve veri üreticileri. Skorlar ve değişiklik raporları bu verilerden türetilmiştir; "
                  "her feed'in lisansı feed panelinde yazar (Licence Ouverte, ODbL…). Feed ve durak adları kaynaktaki hâliyle gösterilir. "
                  "Harita: Plan IGN (IGN-F / Géoplateforme). Resmî tatiller: calendrier.api.gouv.fr (metropol). Ziyaret istatistiği tutulmaz.",
    },
}

ATOM_TITLES = {"fr": f"{NAME} · changements majeurs", "en": f"{NAME} · major changes", "tr": f"{NAME} · önemli değişiklikler"}


# The site's look. This block comes before the page's own <style>, so the selectors are one step
# more specific (html:root, html body) than the page's. Desktop only: wide layout, no narrow mode.
STYLE = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
html:root {
  --ground: #f6f7fb; --surface: #ffffff; --surface-2: #eef1f7; --ink: #111827; --muted: #4b5563; --faint: #6b7280;
  --hair: #dfe3ec; --accent: #1d4ed8; --accent-soft: #e3e9ff; --link: #2563eb; --good: #15803d; --good-soft: #dcfce7;
  --warn: #b45309; --warn-soft: #fef3c7; --bad: #b91c1c; --bad-soft: #fee2e2; --spark: #1d4ed8;
  --font: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
html:root[data-theme="dark"] {
  color-scheme: dark;
  --ground: #0b1020; --surface: #121a2e; --surface-2: #1a2440; --ink: #e6e9f2; --muted: #a8b0c6; --faint: #8089a3;
  --hair: #29355a; --accent: #8ab4ff; --accent-soft: #1c2a4d; --link: #7cc4ff; --good: #4ade80; --good-soft: #12301f;
  --warn: #fbbf24; --warn-soft: #3a2a0c; --bad: #f87171; --bad-soft: #3b1414; --spark: #8ab4ff;
}
@media (prefers-color-scheme: dark) {
  html:root:not([data-theme="light"]) {
    color-scheme: dark;
    --ground: #0b1020; --surface: #121a2e; --surface-2: #1a2440; --ink: #e6e9f2; --muted: #a8b0c6; --faint: #8089a3;
    --hair: #29355a; --accent: #8ab4ff; --accent-soft: #1c2a4d; --link: #7cc4ff; --good: #4ade80; --good-soft: #12301f;
    --warn: #fbbf24; --warn-soft: #3a2a0c; --bad: #f87171; --bad-soft: #3b1414; --spark: #8ab4ff;
  }
}
html body { font-size: 15px; line-height: 1.55; min-width: 1200px; }
html body .wrap { padding-inline: 32px; }
html body .layout { grid-template-columns: minmax(0, 1fr) minmax(600px, 40%); }
html body aside.panel { position: sticky; max-height: calc(100vh - 24px); overflow-y: auto; }
html body .section p { max-width: 120ch; }
html body #totals table { max-width: none; }
html body table.grid { min-width: 1000px; }
html body .pmap { height: 520px; }
html body .pmap.netmap { height: 760px; }
html body .pmap.lmap { height: 560px; }
html body .fname { font-size: 15px; }
html body nav.tabs button { font-size: 15px; }
html body .field label { font-size: 12px; }
</style>
"""


def head() -> str:
    """The page's site <head> block: title, description, feed links and the site's look; no analytics."""
    links = "".join(f'<link rel="alternate" type="application/atom+xml" hreflang="{lang}" title="{escape(ATOM_TITLES[lang])}" '
                    f'href="atom/{lang}/all.xml">\n' for lang in LANGS)
    return (f"<title>{NAME}</title>\n"
            '<meta name="description" content="Feed quality, publication readiness and change history for transport.data.gouv.fr feeds">\n'
            + links + STYLE)


def profile(mdb: dict[str, str] | None = None) -> dict:
    """mdb: {"org/feed": "mdb-…"} (mobilitydb.feed_ids) for links to the Mobility Database."""
    extra = {k: [{"label": "Mobility Database", "url": FEED_PAGE.format(id=v)}] for k, v in sorted((mdb or {}).items())}
    return {
        "site": {
            "name": NAME, "langs": LANGS, "default_lang": "fr", "locale": "fr", "time_zone": "Europe/Paris",
            "regions": region_names(), "tiles": TILES, "tabs": ["overview", "history", "reports"],
            "hide": ["rid", "jpFiles", "memo"], "text": TEXT, "links": LINKS, "feed_links": FEED_LINKS, "feed_extra": extra,
        },
        "head": head(),
        "atom": {"langs": LANGS, "titles": ATOM_TITLES, "author": NAME, "tag": "gtfs-fr-monitor"},
    }
