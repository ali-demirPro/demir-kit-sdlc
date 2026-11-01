# DevOps — Doğrudan dağıtım

**Capability:** `distribution.direct` · **Min level:** expert
**Packs:** `apple-macos`, `launch-readiness`
**Gate:** `behavior`, `platform`, `human`

## Kapsam

App Store dışı dağıtım: paketleme, imzalama, notarization ve güncelleme kanalı.
Her dağıtım geri dönüşü zor olduğu için insan kapısı ister.

## Girdiler

- Leaf seal, hedef sürüm, minimum macOS sürümü.
- İmza kimliği (Developer ID), notarization hesabı, güncelleme kanalı kararı.
- Önceki sürüm ve geri dönüş planı.

## Yöntem

1. **Paket:** `.app` bundle'ı sürümle; DMG veya zip üret; dosya adı sürüm taşır.
2. **İmza:** `codesign --options runtime --timestamp`; iç içe framework'ler
   **içten dışa** imzalanır (en içteki bileşen önce, uygulama bundle'ı en son).
   `codesign --verify --deep --strict` ile doğrula.
3. **Notarization:** `notarytool submit --wait`; ardından bilet **staple**
   edilir. DMG dağıtılıyorsa DMG'ye, zip dağıtılıyorsa `.app`'e (arşivden
   **önce**) staple uygulanır; zip'in kendisi staple edilemez.
4. **Doğrulama:** temiz bir makinede `spctl -a -vv` ve ilk açılış denemesi.
5. **Kanal:** Sparkle veya kendi güncelleme akışı; imzalı appcast; iki kanal
   birlikteyse ADR.
6. **Geri dönüş:** önceki sürümü indirilebilir tut; appcast'i geri al.
7. **Kayıt:** sürüm, imza kimliği, notarization id, yayın zamanı issue'da.

## Kanıt

- Build ve imza logu; `codesign -dv` çıktısı.
- `notarytool` submission id ve `stapler` doğrulaması.
- Temiz makine `spctl` sonucu ve ilk açılış notu.
- Appcast/indirme bağlantısı ve geri dönüş adımı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Paket | Sürümlü, tekrar üretilebilir |
| İmza | Hardened runtime + timestamp |
| Notarization | Bilet staple'lı, `spctl` kabul |
| Kanal | Tek kanal veya ADR'li çift kanal |
| Geri dönüş | Önceki sürüm erişilebilir |
| İnsan | Dağıtım öncesi onay kaydı |

## Anti-pattern'ler

- Notarization'ı "sonra hallederiz" demek.
- Ad-hoc imza ile dağıtım (izinler her rebuild'de sorulur).
- Aynı sürüm numarasıyla iki farklı paket yayınlamak.
- Appcast'i imzasız yayınlamak.
- Geri dönüş planı olmadan yayınlamak.

## Handoff

Release'e: yayın notu, sürüm numarası, indirme bağlantısı.
Tester'a: temiz makine doğrulama adımı ve `spctl` komutu.
