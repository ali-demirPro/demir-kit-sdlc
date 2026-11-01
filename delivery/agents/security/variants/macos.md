# Security — macOS

**Capability:** `platform.macos` · **Min level:** practitioner
**Gate:** `platform`

## Kapsam

Masaüstü uygulamasının güvenlik yüzeyi: sandbox, entitlement, dosya erişimi,
güncelleme kanalı ve sır yönetimi. Mobil kavramlar (jailbreak, ATT) geçerli
değildir.

## Girdiler

- Paket/uygulama, entitlement listesi, imza kimliği.
- Tehdit modeli ve önceki bulgular.
- Güncelleme kanalı ve imza anahtarı konumu.

## Yöntem

1. **Sandbox:** açık mı, hangi entitlement'lar var, her biri gerekçeli mi?
2. **Dosya erişimi:** security-scoped bookmark; keyfi yol erişimi yok.
3. **İmza zinciri:** hardened runtime, timestamp, içten dışa imza.
4. **Notarization:** bilet staple'lı; `spctl` kabul.
5. **Güncelleme kanalı:** imzalı appcast, TLS, bütünlük doğrulaması.
6. **Sırlar:** repoda değil; kısa ömürlü CI kimliği.

## Kanıt

- `codesign -d --entitlements` çıktısı ve minimum yetki gerekçesi.
- `spctl`/`stapler` sonuçları.
- Appcast imza doğrulaması.
- Sırların konumu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Sandbox | Açık, entitlement minimum |
| Dosya | Bookmark, keyfi yol yok |
| İmza | Hardened runtime + timestamp |
| Bilet | Staple'lı, `spctl` kabul |
| Kanal | İmzalı appcast |

## Anti-pattern'ler

- Sandbox'ı performans gerekçesiyle kapatmak.
- Geniş entitlement ile notarization hatasını susturmak.
- İmza anahtarını repoya koymak.

## Handoff

DevOps'a: düzeltilecek entitlement/imza maddesi.
Release'e: dağıtım öncesi güvenlik notu.
