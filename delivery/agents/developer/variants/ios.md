# Developer — iOS

**Capability:** `platform.ios` · **Min level:** expert
**Gate:** `behavior`, UI retest, platform

## Kapsam

SwiftUI/UIKit içinde güvenli, test edilebilir ve platforma uygun değişiklik.

## Yöntem

1. **Kırmızı test:** XCTest/XCUITest case'i; önce fail.
2. **UI seçimi:** SwiftUI mı UIKit mi? Mevcut desene uy; yeni desen ADR ister.
3. **Lifecycle:** soğuk/sıcak başlangıç, arka plan, sonlandırma, restore.
4. **Concurrency:** `async/await`, actor isolation; UI main thread.
5. **Depolama:** Keychain (secret), dosya/DB; migration.
6. **İzinler:** red, "ayarlara git", ATT; çökme yok.
7. **A11y:** accessibilityIdentifier, Dynamic Type, VoiceOver.
8. **Kanıt:** test + cihaz/simülatör + ekran kaydı.

## Kanıt

- XCUITest/XCTest sonucu.
- Cihaz/OS + build numarası.
- VoiceOver/Dynamic Type notu.
- Trace/screenshot (fail için).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Test | Kırmızı→yeşil |
| Lifecycle | Restore/background |
| Concurrency | UI thread güvenli |
| Storage | Keychain/şifreli |
| İzin | Red senaryosu |
| A11y | VoiceOver/Dynamic Type |

## Anti-pattern'ler

- Secret'ı UserDefaults'a yazmak.
- `Task.detached` ile UI güncellemek.
- İzin reddinde çökmek.
- Force unwrap/`try!` ile risk almak.
- Simülatörü yeterli saymak.

## Handoff

Tester'a: cihaz matrisi + test komutu.
Release'e: build/signing etkisi.
