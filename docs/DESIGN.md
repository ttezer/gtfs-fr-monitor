# GTFS-FR monitor — tasarım (3. adım)

Ortak kod `gtfs-jp-monitor`'den gelir (kaynak arayüzü `source.CatalogSource`, 64e45f0;
`matching.compare_from_publication`, b186123). Bu repo yalnız Fransa'ya özgü olanı tutar.

## Feed kimliği

| Alan | Değer | Gerekçe |
|---|---|---|
| `org_id` | veri setinin `datagouv_id`'si (24 hex) | kararlı, dosya yolu kuralına uyar; slug'ların 4'ü uymuyor, en uzunu 147 > 128 |
| `feed_id` | GTFS kaynağının (resource) sayısal kimliği | 487 veri setinin 445'inde tek kaynak; çoklu kaynaklar çoğunlukla ayrı ağlar |
| `feed_name` | tek kaynakta veri seti başlığı; çoklu kaynakta `başlık — kaynak başlığı` | |
| `organization_name` | `publisher.name` | 245 farklı yayıncı |
| `feed_pref_id` | şimdilik yalnız `covered_area` bölge türündeyse bölge INSEE kodu, yoksa `null` | `covered_area`: EPCI 337, belediye 57, departman 48, bölge 31, ülke 7 (+6 karışık). Bölgeye eşleme için tablo gerekir (açık konu, 3e) |
| sürüm `uid` | geçmiş kaydının `uuid`'i (6.386/6.386 UUID v4) | `ids.UID_RE` ile uyumlu |
| `published_at` | `download_datetime`, Europe/Paris saatine çevrilmiş | gelecek gün kesimi bu tarihin günü |
| `from_date` / `to_date` | `feed_info` ya da `resource_metadata` başlangıç/bitiş | |

Kaynak kimlikleri 2025'teki sistem geçişinden beri kararlı; daha eski geçmiş kayıtlarında `resource_id` boş.
Geriye dönük 4 sürüm için yeterli.

## Kapsam

- Yalnız `type = public-transit` ve formatı GTFS olan kaynaklar.
- Hariç: başlığı "Agrégat" ile başlayan 7 veri seti; "Référentiel complet" gibi birleşik kaynaklar (liste: yapılandırma).
- Hariç: son sürümünde `stop_times.txt` ≥ 100 MB (2026-10-13: IDFM, Naolib, TCL, TBM, Aix-Marseille ×2, Fil Bleu, TAO).
  Sitede "şimdilik izlenmiyor" olarak gösterilir.

## Anlamlı sürüm (uygulandı: fingerprint.py, history.py, selection.py, state.py, frsource.py)

1. Aday: geçmişteki her GTFS kaydı (`uuid`, kalıcı URL, `zip_metadata` dosya hash'leri).
2. Ön süzgeç (indirmesiz): referansla aynı dosyalar ya da yalnız metadata dosyaları
   (`feed_info`, `attributions`, `translations`, `object_codes_extension`) değiştiyse indirme yok.
   `calendar_dates` süzülmez: bazı feed'ler onu günde birkaç kez yeniden üretir (Cavalaire: 946 kayıt,
   95 farklı içerik, ardışık kayıtlar hep farklı), ama gerçek değişiklik de onunla gelebilir.
3. Parmak izi (indirme, akışlı): yayın gününden geçerlilik sonuna (en çok 120 gün) her gün için
   hat × yön × ilk/son durak ve saat × durak sayısı × frekans listesinin hash'i; seferi olmayan gün "".
   Geçerlilik sonu = `feed_info` ile takvimin büyüğü (eski kalmış `feed_info` seferleri gizlemesin).
4. Karşılaştırma referansla yapılır: ortak günler, ilk 7 gün (kısa pencerede en çok yarısı) ve
   pencerenin son günü hariç. İlk günler büyük ağların kısa vadeli düzeltmeleri (IDFM: 145 bin
   seferde ~100), son gün çoğu zaman eksik.
   - Fark var → yeni sürüm, dosya referans olur.
   - Ortak gün yok → ardışık tarife → yeni sürüm.
   - İleride hiç sefer yok (süresi geçmiş dosya) → sürüm değil, referans aynı kalır.
   - Fark yok → referans, ileriye dönük günlerinin yarısı geçince yenilenir.
5. Referansla karşılaştırma küçük değişikliklerin birikmesini de yakalar ve günlük feed'lerin durum
   dosyasını çoğu gün değiştirmez (her gün yazılsa veri reposu yılda ~300 MB büyürdü).

Durum: feed başına `catalog/fr-state/<org>/<feed>.json` (sürümler, referans ve parmak izi); yalnız
değişince yazılır.

Başlangıç: geçmiş CSV'sinden geriye doğru örnekleme; adım = pencerenin ileri uzunluğunun yarısı
(1–7 gün), en çok 30 indirme ve 180 gün; son 4 sürüm tutulur, en eskisinin başlangıcı bir adım
kadar kayabilir. Günlük: veri setinin son 25 kaydından en yenisi referansla karşılaştırılır.
Çalışma başına 300 indirme; yetmeyen feed `HISTORY_DEFERRED` notuyla sonraki çalışmaya kalır.
`stop_times` ≥ 100 MB olan feed indirilmeden `FEED_TOO_LARGE` notu alır.

Gerçek veriyle (2026-10-13; L'va, Jybus, Cavalaire, Pays des Ecrins): ilk çalışma 57–78 s, 28–32 indirme,
uyarı yok; ikinci çalışma 7 s, 1 indirme, hiçbir dosya yazılmadı. STAR ve IDFM ardışık çiftleri: fark yok.

## Ülke profili

- Tatil tablosu (uygulandı: profile.py, data/fr_holidays.json): resmî takvim API'si
  `calendrier.api.gouv.fr/jours-feries/metropole.json` (Licence Ouverte), 2006–2031, kaynak sha256 ile.
  Açık konu: Alsace-Moselle (Kutsal Cuma, 26 Aralık) ve denizaşırı bölgeler; şimdilik tek ulusal tablo.
- Motor ayarı (uygulandı): JP varsayılanı + `matching.compare_from_publication: true`; Japonca ad ekleri FR'de etkisiz.
  `run_reports(config=..., holidays_path=...)` ile rapor sürecine verilir (JP 08c0640).
- Doğrulama (2026-10-13): STAR ardışık çifti → teknik, olay yok; L'va Ağustos → Eylül sürümleri → 24/48 hat,
  27 saat değişikliği, 4 kaldırılan ve 2 taşınan durak, major; sınıflandırılmamış satır yok.
- Lisans: `lov2` → `etalab-2.0`, `odc-odbl` → `ODbL-1.0`; `fr-lo`, `mobility-licence`, `notspecified` → `null` (uyarı).
  JP şemasına eklendi (aad9d26); `gtfs_url` deseni FR arşiv sunucusunu kabul ediyor (8f836ff).
- Diller: TR, EN, FR (sayfa ve Atom).

## Alt adımlar

- 3a. (YAPILDI) Repo iskeleti + transport.data.gouv.fr istemcisi (`list_feeds`, kapsam süzgeçleri), testler fixture ile.
- 3b. (YAPILDI) JP'de lisans eşlemesi ve şema listesi.
- 3c. Anlamlı sürüm: ön süzgeç, parmak izi, durum dosyası, `get_generations`. YAPILDI.
- 3d. (YAPILDI) Ülke profili: tatil tablosu, motor ayarı, saat dilimi (published_at Europe/Paris, history.py).
- 3e. (YAPILDI) Sayfa ve Atom dil ayarı (TR/EN/FR), bölge adları. JP: site profili (`export-web --site-profile`,
  data-model §10.4; ea383b7, b0ad8f4, a6e3153), sayfa ve Atom'da Fransızca metinler, dil anahtarı eşitlik testi.
  FR: site.py (profil, IGN Plan karoları, GA'sız başlık), regions.py + data/regions.json (geo.api.gouv.fr;
  557 feed'in 539'unda bölge). JP verisiyle FR profili tarayıcıda denendi: Fransızca arayüz ve rapor, eksik metin yok.
- 3e açık konuları (4. adımda gerçek FR verisiyle): geçmiş tablosundaki JP'ye özgü sütunlar (API konumu `rid`,
  JP dosyaları, not), `signature.py`'deki Japonya sınır kutusu (`coordWarn`), doğrulayıcı seçimi (`notice`, `gtfsjp` sekmesi).
- 4. (YAPILDI, yayın bekliyor) Workflow ve aşamalar. Analiz: GTFS Analyzer, JP ile aynı sabit sürüm (v0.15.0),
  `auto` profili (GTFS-JP kuralları yalnız JP sinyali olan feed'de çalışır), `--lang fr` kural başlıkları.
  FR: `__main__.py` (sync-catalog, analyze, semantic-reports, site-profile), `analyzer.lock.json`,
  `.github/workflows/gtfs-fr-monitor.yml` (JP checkout `jp/` sabit commit). JP 37fc73a (durak alanları,
  kural başlığı dilleri), 34926c5 (geçmiş sütunları gizleme). Yerelde uçtan uca: 4 feed, 8 analiz, 7 rapor,
  FR/EN/TR Atom, sayfa Fransızca ve eksiksiz.
  Yayın için: JP ve FR push; gtfs-fr-data'da ilk commit; `DATA_REPO_TOKEN` secret'ı; Pages kaynağı "GitHub Actions";
  ilk koşular elle (indirme bütçesi ile geçmiş doldurma birkaç koşuya yayılır).

## Ön koşul

`gtfs-jp-monitor`'deki 64e45f0 ve b186123 push edilmeden FR workflow'u ortak kodu GitHub'dan kuramaz.
Yerel geliştirme `../GTFS-JP/src` üzerinden yapılır.
