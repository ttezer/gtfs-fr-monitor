# GTFS-FR Monitor

[Français](README.md) · **English** · [Türkçe](README.tr.md)

Feed quality, publication readiness and change history for the GTFS feeds published on
[transport.data.gouv.fr](https://transport.data.gouv.fr/datasets?type=public-transit).

Every night the monitor reads the French national access point, decides which archived files are
new versions, analyses them with [GTFS Analyzer](https://ttezer.github.io/gtfs-analyzer/), writes a
semantic change report for consecutive versions (lines, stops, trips, timetables, maps) and
publishes a static web site with Atom feeds of the major changes.

Site: https://ttezer.github.io/gtfs-fr-monitor/

## How a version is found

transport.data.gouv.fr republishes many feeds every day, often with a rolling window and rewritten
past days, so a new file is not a new timetable. A file counts as a new version only when the trips
of the days ahead change: per date, each running trip is reduced to its line, direction, first and
last stop with times, stop count and frequencies, and compared with a reference file, leaving out
the next days of short-term adjustments and the last day of a window.

## Layout

| Path | Content |
|---|---|
| `src/gtfs_fr_monitor` | French source: catalogue, archived files, version selection, profile, regions, site profile, command line |
| `src/gtfs_fr_pipeline` | Pipeline: catalog files, analysis, content signatures, reports, classification, impact, export, Atom |
| `src/gtfs_fr_semantic` | Semantic engine: raw diff, matching of stops, lines and trips, the change report |
| `web/prototype/index.html` | The site (one page, data embedded at export) |
| `schemas/` | JSON schemas of the data repository and the reports |

Data is written by the workflow to a separate private repository (`gtfs-fr-data`).

## Running locally

```bash
PYTHONPATH=src python -m unittest discover -t . -s tests
```

```bash
PYTHONPATH=src python -m gtfs_fr_monitor sync-catalog --data-dir data --work-dir work --only ORG_ID/FEED_ID
```

The stages are `gtfs_fr_monitor sync-catalog | analyze | semantic-reports | site-profile` and
`gtfs_fr_pipeline install-analyzer | export-web | record-storage | check-storage`; see
`.github/workflows/gtfs-fr-monitor.yml` for the order. No dependencies beyond Python 3.11
(`jsonschema` for the schema tests).

## Workflow configuration

- `secrets.DATA_REPO_TOKEN`: fine-grained token with contents write on `gtfs-fr-data` only.
- `gtfs-fr-data` needs at least one commit.
- Pages source: GitHub Actions.

## Sources and licences

Feeds: transport.data.gouv.fr and the data producers, under each feed's licence (Licence Ouverte,
ODbL…). Map tiles: Plan IGN (IGN-F / Géoplateforme). Public holidays: calendrier.api.gouv.fr.
Regions: geo.api.gouv.fr. Mobility Database links: MobilityData. Code: MIT.
