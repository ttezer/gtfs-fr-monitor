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

## İçerik testi: ardışık iki ZIP (2026-10-13)

Çiftler: STAR 2026-10-12 00:18 → 2026-10-13 00:19 (~11 MB); IDFM 2026-10-12 18:16 → 2026-10-13 06:21 (~158 MB).

Geçerlilik penceresi: STAR iki ZIP'te de 2026-10-06..18 (`feed_info` aynı); IDFM kayan pencere
(10-09..11-10 → 10-10..11-11).

**Motor 0.7.0, STAR** (40 s, 2,9 GB bellek): 72 hatta `TRIPS_RETIMED`, 9 `SERVICE_REDUCED`; etki minor.
Motor karşılaştırma için 06–12 Ekim'i seçti, yani yeni ZIP'in yayımından önceki günleri. `from_date`
olarak yayın tarihini vermek seçimi değiştirmedi.

**Gün bazında kalkış karşılaştırması** (ilk durak + kalkış saati, hat/yön bazında):

| Feed | Gün | Sefer | Aynı | Kayan | Yalnız eski/yeni |
|---|---|---|---|---|---|
| STAR | 10-12 (geçmiş) | 6.194 → 6.178 | 5.420 | 757 (742'si ≤2 dk) | 17 / 1 |
| STAR | 10-14 | 6.198 | 6.198 | 0 | 0 / 0 |
| IDFM | 10-12 (geçmiş) | 144.803 | 144.796 | 0 | 7 / 7 |
| IDFM | 10-14 | 144.751 | 144.643 | 2 | 106 / 106 |
| IDFM | 10-20 | 134.474 | 134.474 | 0 | 0 / 0 |
| IDFM | 11-05 | 144.343 | 144.343 | 0 | 0 / 0 |

IDFM gün başına ~24 s, ~120 MB bellek (akışlı okuma).

Sonuç:
- Ardışık yeniden üretimler gelecek günlerde neredeyse aynı. Farklar ya geçmiş günlerde (STAR gerçekleşen
  saatleri geri yazıyor gibi [Olası]) ya da kısa vadeli küçük düzeltmelerde.
- Motor FR'de yayın tarihinden sonraki günleri seçmeli; bugün geçmiş günleri seçtiği için STAR'da
  gürültüyü "72 hatta saat değişikliği" diye raporladı. JP'de bu sorun yoktu çünkü yayınlar ileriye dönük.
- Anlamlı sürüm için uygulanabilir kural: her ZIP için gelecekteki ortak günlerde hat/yön bazında
  kalkış parmak izi; parmak izi değişmiyorsa yeni sürüm sayılmaz. Akışlı, ucuz, büyük feed'lerde de çalışır.
- Bellek riski: STAR'da `stop_times` 85 MB → motor 2,9 GB. IDFM `stop_times` 1,1 GB; doğrusal
  ölçeklenirse ~35 GB [Varsayım]. GitHub'ın standart runner'ı 16 GB. IDFM ve agrégat'lar mevcut motorla
  koşamaz; ya başlangıçta dışarıda kalır ya da motorun okuma katmanı akışlı hale getirilir.

## Boyut dağılımı (2026-10-13)

Kaynak: 487 veri setinin `/api/datasets/{id}` geçmişindeki en son GTFS sürümü (`zip_metadata` açılmış boyutları).
553 GTFS kaynağı; 524'ünde `stop_times` boyutu biliniyor, 29'unda geçmiş kaydı yok.

`stop_times.txt` (açılmış): medyan 0,6 MB, p75 3,0, p90 15,5, p99 371, maks 1.110 MB (IDFM).
JP örneği (623 ZIP) karşılaştırma: medyan 0,2, p90 1,8, p99 11,7, maks 97 MB.

| Aralık | Kaynak |
|---|---|
| < 1 MB | 305 |
| 1–10 MB | 146 |
| 10–100 MB | 58 |
| 100–300 MB | 9 |
| ≥ 300 MB | 6 |

100 MB üstü 15 kaynak: 7 agrégat + IDFM (1.110), Naolib/Nantes (576), TAO/Orléans (293),
Aix-Marseille (259 ve 108), TBM/Bordeaux (221), Fil Bleu/Tours (147), TCL/Lyon (130).

Eşiğe göre dışarıda kalan, agrégat olmayan feed'ler:
- 100 MB: IDFM, Aix-Marseille ×2, TCL, TBM, Naolib, Fil Bleu, TAO
- 200 MB: IDFM, Aix-Marseille, TBM, Naolib, TAO
- 300 MB: IDFM, Naolib

Bellek tahmini: STAR 85 MB `stop_times` → 2,9 GB (~34×). Doğrusal varsayımla 300 MB → ~10 GB,
16 GB runner'a sığar; 450 MB üstü sığmaz [Varsayım, ölçülmedi].

En son ZIP'lerin toplamı 1,9 GB (agrégat hariç 1,4 GB) — her sürüm kontrolünde indirilecek üst sınır.

## Repo yapısı (öneri, karar bekliyor)

JP: `gtfs-jp-monitor` (public: kod, workflow, Pages) + `gtfs-jp-data` (private: yalnız Actions yazar).
Pages, workflow'un çalıştığı repodan yayımlanıyor; bir repo = bir site.

FR için:
- `gtfs-fr-monitor` (public, 2026-10-13 açıldı, `origin`): FR workflow'u, FR adaptörü (transport.data.gouv.fr kaynağı, ülke profili), Pages.
  Ortak paketleri (`gtfs_jp_semantic`, diff/sınıflandırma/etki/Atom/sayfa) `gtfs-jp-monitor`'den
  sabit bir commit/tag ile kurar. Bu yerel klasör onun çalışma kopyası olur.
- `gtfs-fr-data` (private, 2026-10-13 açıldı): JP'deki düzenin aynısı; yalnız Actions yazar, ayrı fine-grained token.
- Ön koşul: JP kodunda kaynak arayüzünün ayrılması (pipeline şu an gtfs-data.jp'ye doğrudan bağlı).

## Kalan adımlar

1. ~~Anlamlı sürüm kuralı ve içerik testi.~~ Yapıldı (STAR, IDFM). Açık: motorda gelecek gün seçimi, büyük feed belleği.
2. ~~487 feed'in boyut dağılımı.~~ Yapıldı. Açık: bellek ölçeklenmesini 200–300 MB'lık bir feed'de ölçmek.
3. Agrégat'lar dahil mi?
4. 10–20 FR çiftini 0.7.0 motoruyla karşılaştırmak; Fransızca adlarda eşikler.
5. ODbL yükümlülükleri.
