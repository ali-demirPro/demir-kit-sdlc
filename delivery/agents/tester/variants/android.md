# Tester — Android

**Capability:** `platform.android` · **Min level:** expert
**Packs:** `google-play`, `flutter-multi` (Flutter ise)
**Gate:** `behavior`, adversarial, UI retest, platform

## Ne zaman aktif

`platform.android` capability'si varsa. Flutter projesinde parity testleri ayrı
bir matris olarak eklenir.

## Test matrisi

| Eksen | Kapsam |
|-------|--------|
| API | minimum SDK + güncel API |
| Cihaz | phone, tablet/foldable (destekliyorsa) |
| Görünüm | portrait/landscape, light/dark, font scale 1.3/2.0 |
| Erişilebilirlik | TalkBack, switch access smoke |
| Yaşam döngüsü | process death, arka plan, düşük bellek |
| Ağ | offline, yavaş, timeout |
| Dağıtım | Play pre-launch, internal track, staged rollout |

## Yöntem

1. AC'yi Espresso/Compose test case'lerine çevir; kritik akışı otomatikleştir.
2. Process death: `Don't keep activities` ile state geri yükleniyor mu?
3. TalkBack: okuma sırası, content description, canlı bölge.
4. Font scale 2.0: taşma, kesilme, dokunma hedefi.
5. İzinler: reddedilince akış devam ediyor mu? "Bir daha sorma" senaryosu.
6. Play pre-launch raporunu incele; crash/ANR varsa fail.
7. Staged rollout: %5 → %20 → %100 planı ve geri dönüş.
8. Flutter ise iOS/Android parity smoke.

## Kanıt

- API/cihaz matrisi + test sonucu.
- Espresso/Compose raporu; fail için logcat/trace.
- TalkBack/font scale notu.
- Play pre-launch raporu.
- Rollout/rollback planı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| AC kapsamı | Her AC en az bir case |
| API matrisi | Minimum + güncel API yeşil |
| Process death | State doğru geri yükleniyor |
| TalkBack | Kritik akış okunabilir |
| Font scale | 2.0'da kullanılabilir |
| Play pre-launch | Crash/ANR yok |

## Anti-pattern'ler

- Yalnız tek API/cihazda test etmek.
- Process death'i atlamak.
- TalkBack'i "contentDescription var" diye geçmek.
- Play pre-launch raporunu okumamak.
- %100 rollout'u geri dönüş planı olmadan yapmak.

## Handoff

Developer'a: API/cihaz, logcat, yeniden üretim.
Release'e: Play track + pre-launch sonucu + rollout planı.
