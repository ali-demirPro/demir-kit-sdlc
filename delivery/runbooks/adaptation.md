# Adaptation — proje capability değişimi

Proje capability seti iki kaynaktan gelir:

1. `ecosystem.yaml` yüzeyleri (platform/stack/distribution).
2. `.kit/capabilities.yaml` — açık `include` / `exclude` listesi.

`adapt.py` ikisini birleştirir; **mevcut leaf'leri yeniden mühürlemez**. Yeni
leaf'ler güncel setle açılır.

## Adopt (tek komut)

```bash
# Öneri (yazmaz)
./delivery/scripts/adopt.py --project .

# Kur: init + gerekliyse vendor + standartlar + verify
./delivery/scripts/adopt.py --project . --apply
```

Sıra: `init` → eksikse `vendor_sync` → `standards` → read-only `verify`.
Mevcut dosyalar ezilmez; `--force` init dosyalarını yeniler. Kaynak kit ile
hedef kit çakışırsa (kit'in kendi reposu) yazmadan reddeder. İkinci çalıştırma
idempotenttir.

## Fingerprint

```bash
./delivery/scripts/detect.py --project . --json
```

Read-only tarama: stack, surface, distribution, test komutları, app path ve risk
hotspot. Kök manifest yoksa 1–2 seviye alt dizinler (monorepo) taranır; komutlar
`(cd yol && ...)` biçiminde kapsanır. Çıktı `kit init` için girdidir; hiçbir dosya
yazmaz.

## Init

```bash
# Öneri (yazmaz)
./delivery/scripts/init.py --project .

# Yeni dosyaları yaz; mevcutları atla
./delivery/scripts/init.py --project . --apply

# Mevcut dosyaları da yenile (dikkat)
./delivery/scripts/init.py --project . --apply --force
```

`kit.config.yaml`, `ecosystem.yaml`, `.kit/capabilities.yaml` ve
scripts/gate-behavior.sh üretir. `--apply` varsayılan olarak mevcut dosyayı
ezmez; `--force` açık istekle üzerine yazar.

## Doğrulama

```bash
# Tek proje (yazmaz)
./delivery/scripts/verify.py --project .

# Üç repo kabulü
./delivery/scripts/verify.py \
  --project path/to/web \
  --project path/to/api \
  --project path/to/mobile

# Makine çıktısı
./delivery/scripts/verify.py --project . --json
```

Fingerprint, profil önerisi, capability seti, mevcut `kit.config.yaml` /
`.kit/capabilities.yaml` beyanları ve standartları read-only doğrular.
Yüzey yoksa, bilinmeyen profil/capability varsa veya base profil yoksa sıfırdan
farklı çıkar. `init --apply` öncesi güvenlik kontrolüdür; hiçbir dosya yazmaz.

## Standartlar

Mevcut mühendislik konvansiyonlarını keşfeder ve `AGENTS.md` içine yönetilen bir
blok yazar:

```bash
# Keşif (yazmaz)
./delivery/scripts/standards.py --project .

# AGENTS.md bloğunu yaz/yenile
./delivery/scripts/standards.py --project . --apply

# Blok güncel mi?
./delivery/scripts/standards.py --project . --check
```

Kök ve birinci seviye alt dizinlerdeki manifestleri tarar: `package.json`,
`pyproject.toml`, `go.mod`, `Package.swift`, `Cargo.toml`. Paket yöneticisi,
test/tip/lint/biçim komutları ve stil dosyaları yazılır; tespit edilmeyen komut
uydurulmaz. Blok `demir-kit:standards` işaretleri arasındadır; mevcut
`AGENTS.md` içeriği korunur ve tekrar çalıştırma aynı sonucu verir.

## Profiller

Profil tek seçim değildir; repo birden fazla base ve overlay barındırabilir.
`factory.profiles` listesi base + overlay kompozisyonudur:

```yaml
factory:
  default_profile: web-app
  profiles: [web-app, api-service, auth]
```

- Base: `web-app`, `ios-app`, `android-app`, `flutter-app`, `api-service`,
  `cli`, `library`, `game`, `landing`, `data-ml`
- Overlay: `auth`, `payments`, `offline`, `multi-tenant`, `regulated`,
  `high-scale`

Capability, platform pack, ek gate ve skill'ler birleşir; `default_profile`
listede olmalı ve en az bir base profil bulunmalıdır. Profil yapılandırması
isteğe bağlıdır: eski ürünler profilsiz geçerli kalır.

```bash
# Kompozisyonu gör
./delivery/scripts/profiles.py --project .

# Doğrula (bilinmeyen profil/capability/pack, default, base)
./delivery/scripts/profiles.py --project . --check
```

`init.py` fingerprint'ten çoklu öneri üretir (ör. web + api + auth);
`resolver.py` profil capability'lerini `.kit/capabilities.yaml` ile birleştirir.

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
- Fingerprint `detect.py` ile read-only alınır; `init.py --apply` olmadan
  hiçbir dosya yazılmaz.
- `authority` agent'a atanmaz; capability seviyesi değişse de insan kapısı
  korunur.
