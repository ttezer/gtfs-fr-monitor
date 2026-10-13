"""The French site's profile for gtfs-jp-monitor's page and Atom feeds (its data-model §10.4).

Passed to `export-web --site-profile`. Texts are JSON strings; "{0}", "{1}" stand for the
arguments of the page's own text with the same key.
"""

from __future__ import annotations

from html import escape

from .regions import region_names

NAME = "GTFS-FR Monitor"
SITE_URL = "https://ttezer.github.io/gtfs-fr-monitor/"
LANGS = ["fr", "en", "tr"]

TILES = {
    # Plan IGN v2 from the Géoplateforme (Licence Ouverte), the French counterpart of the GSI tiles.
    "url": "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2"
           "&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
    "label": "Plan IGN",
    "link": "https://geoservices.ign.fr/services-geoplateforme-diffusion",
}

TEXT = {
    "fr": {
        "tagline": "Qualité, préparation à la publication et historique des changements des flux de transport.data.gouv.fr",
        "prefecture": "Région",
        "updated": "Dernière mise à jour il y a {0} ({1}, heure de Paris).",
        "notice": "<b>Aperçu.</b> {0} flux, {1} publications. Une publication est retenue quand les courses des jours à venir changent ; "
                  "les republications quotidiennes sans changement d'horaire ne comptent pas. Les plus grands flux "
                  "(stop_times.txt de 100 Mo ou plus) ne sont pas encore suivis.",
        "footer": "Données : transport.data.gouv.fr et les producteurs. Les scores et rapports de changements sont dérivés de ces données ; "
                  "la licence de chaque flux figure dans son panneau (Licence Ouverte, ODbL…). Les noms de flux et d'arrêts sont affichés "
                  "tels que publiés. Carte : Plan IGN (IGN-F / Géoplateforme). Jours fériés : calendrier.api.gouv.fr (métropole). "
                  "Aucune mesure d'audience.",
    },
    "en": {
        "tagline": "Feed quality, publication readiness and change history for transport.data.gouv.fr feeds",
        "prefecture": "Region",
        "updated": "Last updated {0} ago ({1} Paris time).",
        "notice": "<b>Preview.</b> {0} feeds, {1} publications. A publication counts when the trips of the days ahead change; "
                  "daily republications without a timetable change do not. The largest feeds (stop_times.txt of 100 MB or more) "
                  "are not monitored yet.",
        "footer": "Data: transport.data.gouv.fr and the data producers. Scores and change reports are derived from these data; each feed's "
                  "licence is shown in its panel (Licence Ouverte, ODbL…). Feed and stop names are shown as published. Map: Plan IGN "
                  "(IGN-F / Géoplateforme). Public holidays: calendrier.api.gouv.fr (metropolitan France). No visitor analytics.",
    },
    "tr": {
        "tagline": "transport.data.gouv.fr feed'lerinin kalitesi, yayına hazırlığı ve değişiklik geçmişi",
        "prefecture": "Bölge",
        "updated": "Son güncelleme {0} önce ({1}, Paris saati).",
        "notice": "<b>Önizleme.</b> {0} feed, {1} yayın. Bir yayın, önümüzdeki günlerin seferleri değiştiğinde sayılır; "
                  "tarifesi değişmeyen günlük yeniden yayınlar sayılmaz. En büyük feed'ler (stop_times.txt 100 MB ve üstü) "
                  "henüz izlenmiyor.",
        "footer": "Veri kaynağı: transport.data.gouv.fr ve veri üreticileri. Skorlar ve değişiklik raporları bu verilerden türetilmiştir; "
                  "her feed'in lisansı feed panelinde yazar (Licence Ouverte, ODbL…). Feed ve durak adları kaynaktaki hâliyle gösterilir. "
                  "Harita: Plan IGN (IGN-F / Géoplateforme). Resmî tatiller: calendrier.api.gouv.fr (metropol). Ziyaret istatistiği tutulmaz.",
    },
}

ATOM_TITLES = {"fr": f"{NAME} · changements majeurs", "en": f"{NAME} · major changes", "tr": f"{NAME} · önemli değişiklikler"}


def head() -> str:
    """The page's site <head> block: title, description and feed links; no analytics."""
    links = "".join(f'<link rel="alternate" type="application/atom+xml" hreflang="{lang}" title="{escape(ATOM_TITLES[lang])}" '
                    f'href="atom/{lang}/all.xml">\n' for lang in LANGS)
    return (f"<title>{NAME}</title>\n"
            '<meta name="description" content="Feed quality, publication readiness and change history for transport.data.gouv.fr feeds">\n'
            + links)


def profile() -> dict:
    return {
        "site": {
            "name": NAME, "langs": LANGS, "default_lang": "fr", "locale": "fr", "time_zone": "Europe/Paris",
            "regions": region_names(), "tiles": TILES, "tabs": ["overview", "history", "reports"], "text": TEXT,
        },
        "head": head(),
        "atom": {"langs": LANGS, "titles": ATOM_TITLES, "author": NAME, "tag": "gtfs-fr-monitor"},
    }
