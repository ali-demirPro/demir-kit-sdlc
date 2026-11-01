# Tester — Doğrudan dağıtım

**Capability:** `distribution.direct` · **Min level:** practitioner
**Gate:** `behavior`, `platform`, `human`

## Kapsam

Notarize edilmiş paketin gerçekten çalıştığını doğrulamak: imza, bilet, ilk
açılış ve güncelleme. App Store dağıtımı bu dokümanın kapsamı dışındadır.

## Girdiler

- Paket yolu (DMG/zip), sürüm, hedef minimum macOS sürümü.
- İmza kimliği ve notarization kaydı.
- Temiz test makinesi veya yeni kullanıcı hesabı.

## Yöntem

1. **İmza doğrulaması:** `codesign --verify --deep --strict` ve
   `codesign -dv --verbose=4`; hardened runtime ve timestamp görünmeli.
2. **Bilet:** `spctl -a -vv <app>` ve `xcrun stapler validate <paket>`;
   reddedilirse dağıtım durur.
3. **Temiz kurulum:** paketi indir, aç, ilk çalıştırmada Gatekeeper uyarısı
   çıkmamalı.
4. **Güncelleme:** appcast imzalı mı, yeni sürüm mevcut veriyi koruyor mu?
5. **Geri dönüş:** önceki sürüme dönüş denenir; appcast geri alınabilir mi?
6. **Kayıt:** sürüm, imza kimliği, notarization id ve test makinesi notu.

## Kanıt

- `codesign` ve `spctl` çıktıları.
- `stapler validate` sonucu.
- İlk açılış ve güncelleme ekran görüntüsü/notu.
- Geri dönüş denemesi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| İmza | `codesign --verify` temiz, timestamp var |
| Bilet | `spctl` kabul, staple doğrulandı |
| İlk açılış | Temiz makinede uyarı yok |
| Güncelleme | İmzalı appcast, veri korunuyor |
| Geri dönüş | Önceki sürüm çalışıyor |

## Anti-pattern'ler

- Yalnız geliştirici makinesinde denemek.
- `spctl` çıktısını "yerelde açıldı" ile değiştirmek.
- Güncellemeyi test etmeden yayınlamak.
- Geri dönüş yolunu hiç denememek.

## Handoff

Release'e: doğrulama sonucu ve sürüm notu.
DevOps'a: kırılan imza/bilet adımı ve komut çıktısı.
