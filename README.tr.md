# GTFS-FR Monitor

[Français](README.md) · [English](README.en.md) · **Türkçe**

[transport.data.gouv.fr](https://transport.data.gouv.fr/datasets?type=public-transit)'de yayımlanan
GTFS feed'lerinin kalitesi, yayına hazırlığı ve değişiklik geçmişi.

Monitör her gece Fransa'nın ulusal erişim noktasını okur, arşivlenmiş dosyalardan hangilerinin yeni
sürüm olduğuna karar verir, bunları [GTFS Analyzer](https://ttezer.github.io/gtfs-analyzer/) ile analiz
eder, ardışık sürümler için anlamsal bir değişiklik raporu (hatlar, duraklar, seferler, tarifeler,
haritalar) yazar ve önemli değişikliklerin Atom akışlarıyla birlikte statik bir site yayımlar.

Site: https://ttezer.github.io/gtfs-fr-monitor/

## Sürüm nasıl belirlenir

transport.data.gouv.fr birçok feed'i her gün, çoğu zaman kayan bir pencereyle ve geçmiş günleri
yeniden yazarak yayımlar; yani yeni bir dosya yeni bir tarife demek değildir. Bir dosya ancak
önümüzdeki günlerin seferleri değiştiğinde yeni sürüm sayılır. Her gün için çalışan her sefer hattına,
yönüne, ilk ve son durağıyla saatlerine, durak sayısına ve frekanslarına indirgenir ve bir referans
dosyayla karşılaştırılır; kısa vadeli düzeltmelerin yapıldığı ilk günler ve pencerenin son günü
karşılaştırmaya girmez.

## Yapı

| Yol | İçerik |
|---|---|
| `src/gtfs_fr_monitor` | Fransa kaynağı: katalog, arşiv dosyaları, sürüm seçimi, profil, bölgeler, site profili, komut satırı |
| `src/gtfs_fr_pipeline` | İşlem hattı: katalog dosyaları, analiz, içerik imzaları, raporlar, sınıflandırma, etki, export, Atom |
| `src/gtfs_fr_semantic` | Anlamsal motor: ham fark; durak, hat ve sefer eşleştirme; değişiklik raporu |
| `web/prototype/index.html` | Site (tek sayfa, veri export sırasında gömülür) |
| `schemas/` | Veri reposunun ve raporların JSON şemaları |

Veriyi workflow ayrı ve private bir repoya (`gtfs-fr-data`) yazar.

## Yerelde çalıştırma

```bash
PYTHONPATH=src python -m unittest discover -t . -s tests
```

```bash
PYTHONPATH=src python -m gtfs_fr_monitor sync-catalog --data-dir data --work-dir work --only ORG_ID/FEED_ID
```

Aşamalar `gtfs_fr_monitor sync-catalog | analyze | semantic-reports | site-profile` ve
`gtfs_fr_pipeline install-analyzer | export-web | record-storage | check-storage`; sıra için
`.github/workflows/gtfs-fr-monitor.yml`'a bakın. Python 3.11 dışında bağımlılık yok (şema testleri
için `jsonschema`).

## Workflow ayarları

- `secrets.DATA_REPO_TOKEN`: yalnız `gtfs-fr-data` üzerinde içerik yazma yetkili fine-grained token.
- `gtfs-fr-data`'da en az bir commit olmalı.
- Pages kaynağı: GitHub Actions.

## Kaynaklar ve lisanslar

Feed'ler: transport.data.gouv.fr ve veri üreticileri, her feed kendi lisansıyla (Licence Ouverte,
ODbL…). Harita karoları: Plan IGN (IGN-F / Géoplateforme). Resmî tatiller: calendrier.api.gouv.fr.
Bölgeler: geo.api.gouv.fr. Mobility Database bağlantıları: MobilityData. Kod: MIT.
