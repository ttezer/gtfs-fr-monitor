# GTFS-FR Monitor

**Français** · [English](README.en.md) · [Türkçe](README.tr.md)

Qualité des flux, préparation à la publication et historique des changements des flux GTFS publiés
sur [transport.data.gouv.fr](https://transport.data.gouv.fr/datasets?type=public-transit).

Chaque nuit, le moniteur lit le point d'accès national, détermine quels fichiers archivés sont de
nouvelles versions, les analyse avec [GTFS Analyzer](https://ttezer.github.io/gtfs-analyzer/), rédige
un rapport de changements sémantique entre versions consécutives (lignes, arrêts, courses, horaires,
cartes) et publie un site statique avec des flux Atom des changements majeurs.

Site : https://ttezer.github.io/gtfs-fr-monitor/

## Comment une version est retenue

transport.data.gouv.fr republie de nombreux flux chaque jour, souvent avec une fenêtre glissante et
des jours passés réécrits : un nouveau fichier n'est donc pas un nouvel horaire. Un fichier ne compte
comme nouvelle version que si les courses des jours à venir changent. Pour chaque date, chaque course
est réduite à sa ligne, son sens, ses premier et dernier arrêts avec leurs heures, son nombre d'arrêts
et ses fréquences, puis comparée à un fichier de référence, sans les prochains jours (ajustements à
court terme) ni le dernier jour d'une fenêtre.

## Organisation

| Chemin | Contenu |
|---|---|
| `src/gtfs_fr_monitor` | Source française : catalogue, fichiers archivés, choix des versions, profil, régions, profil du site, ligne de commande |
| `src/gtfs_fr_pipeline` | Chaîne de traitement : fichiers du catalogue, analyse, signatures de contenu, rapports, classification, impact, export, Atom |
| `src/gtfs_fr_semantic` | Moteur sémantique : différence brute, appariement des arrêts, lignes et courses, rapport de changements |
| `web/prototype/index.html` | Le site (une page, données intégrées à l'export) |
| `schemas/` | Schémas JSON du dépôt de données et des rapports |

Les données sont écrites par le workflow dans un dépôt privé distinct (`gtfs-fr-data`).

## Exécution locale

```bash
PYTHONPATH=src python -m unittest discover -t . -s tests
```

```bash
PYTHONPATH=src python -m gtfs_fr_monitor sync-catalog --data-dir data --work-dir work --only ORG_ID/FEED_ID
```

Les étapes sont `gtfs_fr_monitor sync-catalog | analyze | semantic-reports | site-profile` et
`gtfs_fr_pipeline install-analyzer | export-web | record-storage | check-storage` ; l'ordre est celui de
`.github/workflows/gtfs-fr-monitor.yml`. Aucune dépendance au-delà de Python 3.11 (`jsonschema` pour
les tests de schémas).

## Configuration du workflow

- `secrets.DATA_REPO_TOKEN` : jeton à portée fine, écriture du contenu sur `gtfs-fr-data` uniquement.
- `gtfs-fr-data` doit contenir au moins un commit.
- Pages : source « GitHub Actions ».

## Sources et licences

Flux : transport.data.gouv.fr et les producteurs, sous la licence de chaque flux (Licence Ouverte,
ODbL…). Fonds de carte : Plan IGN (IGN-F / Géoplateforme). Jours fériés : calendrier.api.gouv.fr.
Régions : geo.api.gouv.fr. Liens vers la Mobility Database : MobilityData. Code : MIT.
