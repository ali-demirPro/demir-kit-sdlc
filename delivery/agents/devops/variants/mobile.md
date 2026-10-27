# DevOps — Mobile (Apple + Google)

**Capabilities:** `platform.ios`, `platform.android`, `distribution.app_store`, `distribution.play` · **Min level:** expert
**Gate:** `platform`, `commercial`, `human`

## Kapsam

Mobil build/signing/track yönetimi, cihaz matrisi, kademeli rollout ve crash
takibi.

## Yöntem

1. **Build:** reproducible; build numarası; artefakt saklama.
2. **Signing:** iOS sertifika/provisioning; Android keystore; sır saklama.
3. **Track:** TestFlight/internal → beta → prod; Play internal → closed → open.
4. **Cihaz/OS:** destek matrisi; min sürüm; tablet/foldable.
5. **Rollout:** iOS phased release; Play staged %5→%20→%100.
6. **Crash:** symbol upload; crash-free oranı; alarm.
7. **Rollback:** iOS önceki build; Android halt/rollback.
8. **Store:** metadata/privacy ile build tutarlı mı?

## Kanıt

- Build/signing kanıtı (sır değil).
- Track/rollout planı.
- Cihaz/OS matrisi.
- Crash-free eşiği + alarm.
- Rollback adımı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Build | Reproducible + numara |
| Signing | Sır repo dışı |
| Track | Kademeli |
| Cihaz | Destek matrisi |
| Crash | Symbol + eşik |
| Rollback | Test edilmiş |

## Anti-pattern'ler

- Debug build'i store'a göndermek.
- Keystore'u repoya koymak.
- %100 rollout'u test etmeden açmak.
- Crash symbol'ünü yüklememek.
- Store metadata'sını build'den bağımsız yazmak.

## Handoff

Release'e: track/rollout kanıtı.
Tester'a: build + cihaz matrisi.
Security'ye: signing/secret.
