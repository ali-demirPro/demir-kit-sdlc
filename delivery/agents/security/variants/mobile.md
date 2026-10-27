# Security — Mobile (iOS + Android)

**Capabilities:** `platform.ios`, `platform.android`, `distribution.app_store`, `distribution.play` · **Min level:** expert
**Gate:** `platform`, `commercial` + security review

## Kapsam

Mobil depolama, ağ, platform izinleri, jailbreak/root, privacy manifest ve store
güvenlik gereksinimleri.

## Yöntem

1. **Depolama:** keychain/keystore; dosya şifreleme; yedekleme politikası.
2. **Ağ:** ATS (iOS), network security config (Android), pinning ihtiyacı.
3. **Kimlik:** token saklama, biometric, cihaz bağlama, logout.
4. **Platform:** jailbreak/root tespiti; debug flag; URL scheme.
5. **İzinler:** minimum izin; gerekçe; red senaryosu.
6. **Privacy:** privacy manifest (iOS), data safety (Play), ATT.
7. **Store:** imza, entitlement, inceleme riski.
8. **Bulgular:** `SEC-*`, severity, cihaz/OS.

## Kanıt

- Depolama/ağ kontrolü.
- İzin matrisi.
- Privacy manifest/data safety taslağı.
- Jailbreak/root testi.
- `SEC-*` kapatma kanıtı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Storage | Keychain/keystore |
| Network | ATS/network config |
| Auth | Token/biometric güvenli |
| Platform | Debug/root kontrolü |
| Privacy | Manifest/data safety |
| Store | İmza/entitlement tutarlı |

## Anti-pattern'ler

- Token'ı UserDefaults/SharedPreferences'a yazmak.
- ATS'i tamamen kapatmak.
- Gereksiz izin istemek.
- Privacy manifest'i boş bırakmak.
- Jailbreak tespitini "kırılmaz" sanmak.

## Handoff

Developer'a: depolama/ağ/izin düzeltmesi.
Tester'a: cihaz/OS güvenlik senaryoları.
Release'e: privacy/data safety.
Architect'e: trust boundary.
