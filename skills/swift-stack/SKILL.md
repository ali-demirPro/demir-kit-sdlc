---
name: swift-stack
description: >-
  Swift 6 ve SwiftUI/AppKit pratiği: izolasyon, SwiftData geçişi, köprü sınırı,
  CLI'dan build ve imza tuzakları. Use when a macOS leaf writes Swift code,
  when a SwiftData migration or AppKit bridge is needed, or when the build or
  signature fails.
---

# swift-stack

macOS tarafında kod yazarken en sık kırılan beş yer. Her biri kısa kural ve
kanıt ile gelir.

## 1 — Eşzamanlılık

- Projede default MainActor izolasyonu açıksa koru; değilse UI tiplerini açıkça
  `@MainActor` işaretle.
- UI dışı iş `Sendable` sınırından geçer; sınırı dar tut.
- `Task.detached` içinden UI güncellemesi yasak.

Kanıt: derleme uyarısı yok + ilgili test.

## 2 — SwiftData ve geçiş

- Yeni alan **varsayılan değerle** eklenir; mevcut store açılmaya devam eder.
- Yıkıcı değişimde migration planı ve geri dönüş yazılır.
- Store konumu tek yerde tanımlıdır; test store'u `/tmp` altındadır.

Kanıt: eski store ile açılış testi.

## 3 — AppKit köprüsü

- `NSViewRepresentable` yalnız native kontrol yetmediğinde kullanılır.
- Köprü tek sorumluluk taşır; iş mantığı SwiftUI tarafında kalır.

Kanıt: köprüyü saran view'ın snapshot'ı + etkileşim testi.

## 4 — CLI'dan build ve imza

```bash
swift build -c release
# .app bundle'ını betikle paketle (veya xcodebuild)
codesign --force --options runtime --timestamp --sign "<identity>" MyApp.app
codesign --verify --deep --strict MyApp.app
```

- `swift build` çıplak bir executable üretir; `.app` bundle'ı ayrı adımdır.
- İç içe framework'ler **içten dışa** imzalanır.
- İzinler imzaya ve yola bağlıdır; ad-hoc imza her rebuild'de izin sorar.

Kanıt: build logu + `codesign` çıktısı.

## 5 — Tanılama

- Debug çıktısı stderr'e, ortam bayrağı arkasında.
- Kullanıcı verisi ve sır loglanmaz.
- SPM "not in scope" hatasında scratch path temizlenir.

Kanıt: tekrarlanabilir komut + çıktı.

## Anti-pattern'ler

- Force unwrap / `try!` ile hızlı yol.
- Sandbox'ı kapatıp sonra düzeltmek.
- Migration'ı "kullanıcı az" diye atlamak.
- Test için kullanıcının store'una yazmak.

## Done when

Değişen Swift dosyaları derleniyor, ilgili test veya self-test yeşil ve build/imza
komutu tekrar çalıştırılabilir durumda.
