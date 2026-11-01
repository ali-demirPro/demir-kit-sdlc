# Developer — macOS

**Capability:** `platform.macos` · **Min level:** expert
**Gate:** `behavior`, UI retest, platform

## Kapsam

SwiftUI + AppKit köprüsü, Swift 6 eşzamanlılığı, yerel depolama, sandbox ve
komut satırından build/imza. Xcode GUI'si varsayılmaz.

## Girdiler

- Leaf seal, AC, `tests_plan` case'leri.
- Minimum macOS sürümü, hedef mimari, mevcut build betiği.
- Design system ve `UI/` dosya düzeni; varsa `ARCHITECTURE.md`.

## Yöntem

1. **Kırmızı test:** saf mantık için birim test; davranış için self-test case'i.
   Önce fail.
2. **İzolasyon:** projede default MainActor izolasyonu açıksa onu koru; değilse
   UI tiplerini açıkça `@MainActor` işaretle. UI dışı iş `Sendable` sınırından
   geçer; `Task.detached` ile UI güncellenmez.
3. **SwiftData/depolama:** şema değişiminde varsayılan değer; migration planı;
   store yolu tek yerde tanımlı.
4. **AppKit köprüsü:** `NSViewRepresentable` sınırı dar; native kontrol
   yetiyorsa köprü yazılmaz.
5. **Dosya erişimi:** sandbox açıkken security-scoped bookmark; minimum
   entitlement.
6. **Arka plan işi:** `NSBackgroundActivityScheduler`, App Nap farkındalığı; uzun
   iş görünür ilerleme bildirir.
7. **Build:** `swift build` ile derle, `.app` bundle'ını betikle (veya
   `xcodebuild`) paketle → `codesign`; notarization ayrı adım. Hata ilk
   satırdan okunur.
8. **Tanılama:** debug çıktısı stderr'e, ortam bayrağı arkasında.

## Kanıt

- Test çıktısı (birim + self-test) ve gate exit 0.
- Build ve imza logu; notarization sonucu (dağıtım varsa).
- Değişen dosya listesi ve `ARCHITECTURE.md` etkisi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Test | Kırmızı → yeşil, self-test exit 0 |
| Eşzamanlılık | UI thread güvenli, `Sendable` sınırı açık |
| Depolama | Migration ve varsayılan değer var |
| Sandbox | Minimum entitlement, bookmark ile dosya |
| Build | CLI'dan tekrarlanabilir, imza adımı tanımlı |
| Tanılama | stderr + bayrak, kullanıcı verisi loglanmaz |

## Anti-pattern'ler

- `Task.detached` içinden UI güncellemek.
- Force unwrap / `try!` ile risk almak.
- Test için kullanıcının gerçek veritabanına yazmak (`/tmp` store kullan).
- Xcode GUI'sine bağımlı build; imzayı elle yapmak.
- Sandbox'ı kapatıp "sonra açarız" demek.

## Handoff

Tester'a: çalıştırma komutu, test store yolu, self-test kapsamı.
Release'e: imza/notarization etkisi ve dağıtım kanalı.
