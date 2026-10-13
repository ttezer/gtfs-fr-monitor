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

## Anlamlı sürüm ölçümü (2026-10-13, 11 feed, yalnız CSV metadata)

Kurallar: R0 = her farklı ZIP; R1 = yalnız `calendar_dates`/`feed_info`/`attributions`/
`object_codes_extension`/`translations` değişimi sayılmaz; R2 = `agency`/`routes`/`stops` değişmeli;
+Ng = son seçilenden en az N gün sonra. Hücre: son 12 aydaki sürüm (son 4 sürümün kapsadığı gün).

| Feed | R0 | R1 | R2 | R1+7g | R1+30g |
|---|---|---|---|---|---|
| IDFM (668) | 699 (1) | 699 (1) | 485 (1) | 41 (21) | 10 (90) |
| Agrégat Grand Est (1344) | 612 (0) | 610 (0) | 529 (0) | 45 (21) | 11 (91) |
| Agrégat AURA (732) | 401 (0) | 401 (0) | 184 (1) | 41 (21) | 11 (91) |
| STAR (507) | 432 (2) | 431 (2) | 75 (15) | 48 (21) | 12 (91) |
| TADAO (606) | 41 (39) | 41 (39) | 12 (46) | 15 (119) | 8 (150) |
| L'va (566) | 20 (41) | 19 (41) | 19 (41) | 12 (82) | 7 (133) |
| T2C (850) | 14 (100) | 14 (100) | 14 (100) | 11 (107) | 6 (185) |
| Cavalaire (1063) | 120 (27) | 1 (381) | 1 (382) | 1 (394) | 1 (445) |
| Pays des Ecrins (1322) | 60 (128) | 2 | 2 | 2 | 2 |
| Jybus (687) | 3 (358) | 3 | 3 | 3 | 3 |
| Le 37 (1372) | 2 | 2 | 2 | 2 | 1 |

Sonuç:
- Dosya-hash süzgeci (R1) küçük feed'lerde gürültüyü temizliyor (Cavalaire 120 → 1).
- Büyük feed'lerde işe yaramıyor: her yeniden üretimde `trips`/`stop_times`, çoğu zaman `stops`/`routes` da değişiyor.
- Zaman aralığı deterministik ama keyfi; gerçek değişikliği gürültüden ayırmaz.
- Büyük feed'ler için içerik düzeyinde test gerekli: ardışık iki ZIP'i 0.7.0 motoruyla karşılaştırıp
  anlamsal farkın sıfıra yakın olup olmadığına bakmak (ZIP indirmesi gerekir; IDFM ~158 MB).

## Repo yapısı (öneri, karar bekliyor)

JP: `gtfs-jp-monitor` (public: kod, workflow, Pages) + `gtfs-jp-data` (private: yalnız Actions yazar).
Pages, workflow'un çalıştığı repodan yayımlanıyor; bir repo = bir site.

FR için:
- `gtfs-fr-monitor` (public): FR workflow'u, FR adaptörü (transport.data.gouv.fr kaynağı, ülke profili), Pages.
  Ortak paketleri (`gtfs_jp_semantic`, diff/sınıflandırma/etki/Atom/sayfa) `gtfs-jp-monitor`'den
  sabit bir commit/tag ile kurar. Bu yerel klasör onun çalışma kopyası olur.
- `gtfs-fr-data` (private): JP'deki düzenin aynısı; yalnız Actions yazar, ayrı fine-grained token.
- Ön koşul: JP kodunda kaynak arayüzünün ayrılması (pipeline şu an gtfs-data.jp'ye doğrudan bağlı).

## Kalan adımlar

1. ~~Anlamlı sürüm kuralını örnek CSV'lerde ölçmek.~~ Yapıldı; büyük feed'ler için içerik testi açık.
2. 487 feed'in boyut dağılımı; 100 MB üstü ZIP ve Actions süresi.
3. Agrégat'lar dahil mi?
4. 10–20 FR çiftini 0.7.0 motoruyla karşılaştırmak; Fransızca adlarda eşikler.
5. ODbL yükümlülükleri.
