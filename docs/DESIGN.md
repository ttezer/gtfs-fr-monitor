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

## Anlamlı sürüm

1. Aday: geçmişteki her GTFS kaydı. `zip_metadata` sha256 kümesi bir öncekiyle aynıysa aday değil.
2. Ön süzgeç (indirmesiz): yalnız `calendar_dates`/`feed_info`/`attributions`/`translations`
   değiştiyse ve yeni ZIP'in geçerlilik aralığı aynıysa aday değil.
3. Parmak izi (indirme): yayın gününden sonraki ortak günlerde, gün × hat × yön × ilk durak
   kalkış saatleri kümesinin sha256'sı. Önceki anlamlı sürümle aynıysa sürüm değil.
4. Değiştiyse yeni anlamlı sürüm → katalogda yeni generation.

Durum (son incelenen aday, son anlamlı sürümün parmak izi) veri reposunda feed başına
`catalog/fr-state/<org>/<feed>.json` dosyasında tutulur; tekrar indirme olmaz.

Başlangıç: geçmiş CSV'sinden geriye doğru en fazla 4 anlamlı sürüm. Günlük: `/api/datasets/{id}`
geçmişindeki (son 25 kayıt) yeni adaylar.

## Ülke profili

- Tatil tablosu: Fransa resmî tatilleri (Paskalya'ya bağlı günler hesaplanır), `gtfs-jp-semantic-holidays/1` şemasında.
- Motor ayarı: JP varsayılanı + `matching.compare_from_publication: true`; Japonca ad ekleri FR'de etkisiz.
- Lisans: `lov2` → `etalab-2.0`, `odc-odbl` → `ODbL-1.0`; `fr-lo`, `mobility-licence`, `notspecified` → `null` (uyarı).
  JP şemasındaki lisans listesine bu iki kimliğin eklenmesi gerekir.
- Diller: TR, EN, FR (sayfa ve Atom).

## Alt adımlar

- 3a. Repo iskeleti + transport.data.gouv.fr istemcisi (`list_feeds`, kapsam süzgeçleri), testler fixture ile.
- 3b. JP'de lisans eşlemesi ve şema listesi.
- 3c. Anlamlı sürüm: ön süzgeç, parmak izi, durum dosyası, `get_generations`.
- 3d. Ülke profili: tatil tablosu, motor ayarı, saat dilimi.
- 3e. Sayfa ve Atom dil ayarı (TR/EN/FR), bölge adları.
- 4. `gtfs-fr-data` düzeni ve workflow.

## Ön koşul

`gtfs-jp-monitor`'deki 64e45f0 ve b186123 push edilmeden FR workflow'u ortak kodu GitHub'dan kuramaz.
Yerel geliştirme `../GTFS-JP/src` üzerinden yapılır.
