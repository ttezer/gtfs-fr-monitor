# GTFS-FR monitor — fizibilite notları

Başlangıç: 2026-10-13. Amaç: gtfs-jp-monitor'ün (`/Users/tacettintezer/Projeler/GTFS-JP`) Fransa karşılığı.

## Mimari öneri

Kopya repo değil; tek kod tabanı + ülke adaptörü. JP'ye bağlı kısımlar:

- Kaynak: `gtfsdatajp.py`, `catalog.py`, `download.py`, `ids.py`, `licenses.py`
- Ülke verisi: `gtfs_jp_semantic/data/jp_holidays.json`, `default_config.json` (ad ekleri), `lines.py` (Japonca karakter kuralları)
- Sunum: saat dilimi (+09:00), `atom.py`, `webexport.py`

Motor, diff, sınıflandırma, etki, Atom ve sayfa genel.

## Feed sayıları (Mobility Database `feeds_v2.csv`, 2026-10-13)

FR GTFS Schedule: 774 (active 488, inactive 80, deprecated 205, future 1). JP: 647.

## Kaynak: transport.data.gouv.fr

- `/api/datasets`: 487 GTFS veri seti, 566 GTFS kaynağı. Token gerekmez.
- Lisans: lov2 311, odc-odbl 161, notspecified 10, fr-lo 3, mobility-licence 2 (IDFM).
- 7 "Agrégat" bölgesel toplu feed (yerel feed'leri tekrarlar).
- `/api/datasets/{id}` → `history`: tüm formatlar karışık, son 25 girdi. Yetersiz.
- Tam geçmiş: `/datasets/{numeric_id}/resources_history_csv`
  (`resource_history_id, resource_id, permanent_url, payload, inserted_at`;
  payload'da `zip_metadata[].sha256`, `filesize`, `download_datetime`).
  2021'den kalan `permanent_url` dosyaları erişilebilir (HTTP 200).

## Asıl sorun: sık yeniden yayın

| Feed | Farklı içerikli sürüm | Dönem | Toplam boyut |
|---|---|---|---|
| IDFM | 699 | 2025-12 → 2026-10 | 89,7 GB (~158 MB/ZIP) |
| Agrégat (bölgesel) | 938 | 2022 → | 79,1 GB |
| STAR | 1.262 | 2021 → | 12,9 GB |
| L'va | 1.146 | 2021 → | 3,0 GB |
| T2C | 53 | 2022 → | 0,2 GB |
| Jybus | 16 | 2022 → | <0,01 GB |

Büyük feed'ler günde birkaç kez yeniden üretiliyor (`calendar_dates`, `stop_times`, `trips` her seferinde değişiyor).
JP'deki "yayın" kavramına denk değil.

## Kararlar

- Başlangıçta feed başına geriye dönük 4 sürüm (JP'de de öyle başlandı).
- Öneri (onay bekliyor): "4 anlamlı sürüm" — `feed_info` sürümü/geçerlilik aralığı ya da
  `routes`/`stops`/sefer yapısı değişen sürümler; yalnız `calendar_dates` değişimi sayılmaz.
  CSV'deki hash'lerden indirmeden hesaplanabilir.

## Kalan adımlar

1. Anlamlı sürüm kuralını örnek CSV'lerde ölçmek.
2. 487 feed'in boyut dağılımı; 100 MB üstü ZIP ve Actions süresi.
3. Agrégat'lar dahil mi?
4. 10–20 FR çiftini 0.7.0 motoruyla karşılaştırmak; Fransızca adlarda eşikler.
5. ODbL yükümlülükleri.
