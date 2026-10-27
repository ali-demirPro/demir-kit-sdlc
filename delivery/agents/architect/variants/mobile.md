# Architect — Mobile (iOS + Android)

**Capabilities:** `platform.ios`, `platform.android` · **Min level:** expert
**Gate:** `architect`, `platform`

## Kapsam

Mobil uygulama mimarisi: lifecycle, yerel depolama, offline/sync, arka plan,
izinler, dağıtım kısıtları ve platform farkları.

## Yöntem

1. **Platform sınırı:** ortak çekirdek + platform adapter; parity nerede?
2. **Lifecycle:** soğuk/sıcak başlangıç, arka plan, sonlandırma, restore.
3. **Depolama:** keychain/keystore, dosya, DB; şifreleme ve migration.
4. **Offline/sync:** kaynak-of-truth, çakışma, kuyruk, idempotency.
5. **İzinler:** reddedilme, "bir daha sorma", ayarlara yönlendirme.
6. **Arka plan işleri:** iOS background task / Android WorkManager sınırı.
7. **Dağıtım:** imza, TestFlight/Play track, sürüm uyumluluğu.
8. **NFR:** startup, bellek, pil, ağ, cihaz matrisi.

## Kanıt

- `ADR-*`: ortak çekirdek vs platforma özgü karar.
- Lifecycle/offline state diyagramı.
- Depolama ve migration planı.
- İzin/akış matrisi.
- Cihaz/OS destek matrisi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Paylaşım | Ortak/özgü sınır gerekçeli |
| Lifecycle | Restore/background tasarlı |
| Offline | Çakışma ve kuyruk tanımlı |
| Depolama | Şifreleme + migration |
| İzin | Red senaryosu var |
| Dağıtım | Track/imza planı |

## Anti-pattern'ler

- Web mantığını mobile'a kopyalamak.
- Offline'ı "sonra ekleriz" demek.
- İzin reddini çıkmaz yapmak.
- Platform farkını tek kod tabanında gizlemek.
- TestFlight/Play track'i sürüm planına koymamak.

## Handoff

Developer'a: adapter sınırı + state diyagramı.
Tester'a: cihaz/OS matrisi + lifecycle/offline senaryoları.
Release'e: imza/track planı.
