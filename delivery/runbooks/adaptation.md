# Adaptation — proje capability değişimi

Proje capability seti iki kaynaktan gelir:

1. `ecosystem.yaml` yüzeyleri (platform/stack/distribution).
2. `.kit/capabilities.yaml` — açık `include` / `exclude` listesi.

`adapt.py` ikisini birleştirir; **mevcut leaf'leri yeniden mühürlemez**. Yeni
leaf'ler güncel setle açılır.

## Dosya

```yaml
# .kit/capabilities.yaml — adapt.py yönetir
version: 1
include: [platform.android]
exclude: []
source: adapt.py
updated: 2026-10-27T…
```

- `include`: ecosystem'den türetilmese bile aktif say.
- `exclude`: ecosystem türetse bile pasif say.
- Çakışma: `include` önce uygulanır, `exclude` sonra kaldırır.

## Akış

```bash
# Sadece farkı gör (yazmaz)
./delivery/scripts/adapt.py --add platform.android

# Uygula
./delivery/scripts/adapt.py --add platform.android --apply

# Kaldır
./delivery/scripts/adapt.py --remove platform.web --apply
```

Çıktı: capability/rol/variant/gap/risk farkı. `--json` makine çıktısı verir.

## Örnek: web → web + Android

- `platform.android` eklenir; Android capability'si aktif olur.
- `designer`, `developer`, `tester`, `architect`, `devops`, `security`,
  `marketing/stores` Android variant'ları açılır.
- Web variant'ları korunur; iOS pasif kalır.
- Kapanmış leaf'ler değişmez; yeni Android leaf'i `surfaces: [android.app]` ile
  mühürlenir.

## Örnek: iOS → web

```bash
./delivery/scripts/adapt.py --add platform.web --remove platform.ios --apply
```

- `platform.web` aktif, `platform.ios` pasif olur.
- iOS'a özel dokümanlar yüklenmez; web variant'ları yüklenir.
- Yalnız `--add platform.web` iOS'u **kapatmaz**; iki platform birlikte kalır.

## Doğrulama

```bash
./delivery/scripts/adapt.py --add platform.android --json
./delivery/scripts/doctor.sh --product --root .
./delivery/scripts/doctor.sh --issue <yeni-leaf>
```

`doctor --product`, `.kit/capabilities.yaml` içindeki bilinmeyen capability'leri
reddeder.

## Rollback

`exclude`'a al veya dosyayı git ile geri al; yeni leaf'ler eski sete döner.
Kapanmış leaf'lerin evidence'ı silinmez.

## Sınırlar

- `adapt.py` `ecosystem.yaml`'ı **değiştirmez**; yüzey bilgisi orada kalır.
- Fingerprint/otomatik tarama #56 kapsamı dışındadır; surface bilgisi insan
  tarafından girilir.
- `authority` agent'a atanmaz; capability seviyesi değişse de insan kapısı
  korunur.
