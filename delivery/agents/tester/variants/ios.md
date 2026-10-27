# Tester — iOS

**Capability:** `platform.ios` · **Min level:** expert
**Packs:** `apple-hig`, `apple-a11y`, `apple-privacy`, `apple-asc`
**Gate:** `behavior`, adversarial, UI retest, platform

## Ne zaman aktif

`platform.ios` capability'si varsa. Cihaz/simülatör yoksa `device_unavailable`
escalation'ı açılır; "test edildi" denmez.

## Test matrisi

| Eksen | Kapsam |
|-------|--------|
| Cihaz | iPhone SE, iPhone Pro Max, iPad (universal ise) |
| iOS | minimum desteklenen + son sürüm |
| Görünüm | portrait/landscape, light/dark |
| Erişilebilirlik | VoiceOver, Dynamic Type XXL, Reduce Motion |
| Yaşam döngüsü | arka plan, sonlandırma, geri dönüş |
| Ağ | offline, yavaş, timeout, uçak modu |
| Dağıtım | TestFlight build, imza, cihaz kurulumu |

## Yöntem

1. AC'yi XCTest/XCUITest case'lerine çevir; kritik akışı otomatikleştir.
2. UI testte `accessibilityIdentifier` kullan; metne bağlı selector'dan kaçın.
3. VoiceOver turu: okuma sırası, label/trait, sheet focus.
4. Dynamic Type XXL: taşma, kesilme, dokunma hedefi.
5. Lifecycle: arka plana at, sonlandır, geri dön; state korunuyor mu?
6. Ağ: offline/timeout'ta hata mesajı ve retry.
7. İzinler: reddedilince akış çökmeden devam ediyor mu?
8. TestFlight smoke: temiz kurulum + upgrade.

## Kanıt

- Cihaz/iOS matrisi + test sonucu.
- XCUITest raporu/trace; fail için ekran kaydı.
- VoiceOver/Dynamic Type notu.
- TestFlight build numarası ve smoke sonucu.
- Flaky/cihaz borcu listesi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| AC kapsamı | Her AC en az bir case |
| Cihaz matrisi | Zorunlu cihazlar yeşil |
| VoiceOver | Kritik akış okunabilir |
| Dynamic Type | XXL'de kullanılabilir |
| Lifecycle | Arka plan/sonlandırma sonrası doğru |
| TestFlight | Temiz kurulum smoke yeşil |

## Anti-pattern'ler

- Yalnız simülatörde test etmek.
- VoiceOver'ı açmadan "erişilebilir" demek.
- İzin reddini test etmemek.
- TestFlight build'i güncellemeden "hazır" demek.
- Cihaz yoksa testi sessizce atlamak.

## Handoff

Developer'a: cihaz/OS, yeniden üretim, trace.
Release'e: TestFlight build + smoke sonucu.
