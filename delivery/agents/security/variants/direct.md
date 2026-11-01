# Security — Doğrudan dağıtım

**Capability:** `distribution.direct` · **Min level:** practitioner
**Gate:** `behavior`, `platform`, `human`

## Kapsam

App Store dışı dağıtımın güvenlik yüzeyi: imza zinciri, hardened runtime,
entitlement'lar, güncelleme kanalı ve gizli anahtar hijyeni.

## Girdiler

- Paket, imza kimliği, entitlement listesi.
- Güncelleme kanalı (appcast, indirme uç noktası).
- Tehdit modeli ve varsa önceki bulgular.

## Yöntem

1. **İmza zinciri:** Developer ID, iç içe framework'lerin içten dışa imzalanması,
   hardened runtime ve timestamp denetimi.
2. **Entitlement:** minimum yetki; `com.apple.security.*` listesi gerekçeli;
   geçici istisna (temporary exception) yok.
3. **Notarization kanıtı:** biletin staple'lı olması; `spctl` kabulü.
4. **Güncelleme kanalı:** appcast imzası, TLS, indirme bütünlüğü; kanal ele
   geçirilirse ne olur?
5. **Sırlar:** imza anahtarı ve notarization kimliği repoda değil; CI'da
   kısa ömürlü kimlik.
6. **Log/gizlilik:** kullanıcı verisi ve anahtar loglanmıyor.

## Kanıt

- `codesign -d --entitlements` çıktısı ve minimum yetki gerekçesi.
- İmza zinciri ve timestamp notu.
- Appcast imza doğrulaması.
- Sırların nerede tutulduğuna dair kısa kayıt.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| İmza zinciri | İçten dışa, hardened runtime, timestamp |
| Entitlement | Minimum, gerekçeli, istisnasız |
| Bilet | Staple'lı, `spctl` kabul |
| Kanal | İmzalı appcast, bütünlük doğrulaması |
| Sırlar | Repo dışında, kısa ömürlü |

## Anti-pattern'ler

- Sandbox/hardened runtime'ı "dağıtımda sorun çıkarıyor" diye kapatmak.
- Geniş entitlement ile notarization hatasını susturmak.
- İmzasız appcast yayınlamak.
- İmza anahtarını repoya veya CI değişkenine düz metin koymak.

## Handoff

DevOps'a: düzeltilecek imza/entitlement maddesi.
Release'e: dağıtım öncesi güvenlik onayı.
