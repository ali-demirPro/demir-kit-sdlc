# Designer — macOS

**Capability:** `platform.macos` · **Min level:** expert
**Packs:** `apple-hig`, `apple-a11y`, `apple-privacy`, `apple-asc`
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Kapsam

Pencere, menü çubuğu, toolbar, klavye ve masaüstü etkileşimi. Dokunmatik
alışkanlıklar (safe area, tab bar, swipe-back) burada geçerli değildir.

## Girdiler

- Leaf seal, AC, hedef minimum macOS sürümü.
- Pencere listesi: ana pencere, Settings, panel, inspector.
- Menü haritası ve kısayol envanteri; mevcut design system.
- HIG referansı ve varsa Liquid Glass gereksinimi (macOS 26+).

## Yöntem

1. **Pencere modeli:** kaç pencere? Settings ayrı mı, panel mi, inspector mı?
   Aynı işi iki pencerede yaptırmıyorsun.
2. **Navigation:** `NavigationSplitView` + sidebar; toolbar öğeleri tek satırda
   anlamlı mı, overflow davranışı tanımlı mı?
3. **Menü çubuğu:** her komut bir menüde; File/Edit/View/Window/Help dolu;
   Window menüsü pencere listesini taşır.
4. **Klavye:** her komuta kısayol, çakışma yok; Full Keyboard Access ile
   ulaşılamayan kontrol yok.
5. **Kontrol seçimi:** native kontrol; web benzeri custom kontrol yerine
   toolbar, sidebar, context menu, date picker.
6. **Tipografi ve ölçü:** sistem font, 13 pt gövde, 4 pt ızgara; sabit punto
   yok.
7. **Boş durum:** ilk eylemi önerir; boş ekran "hiçbir şey yok" demez.
8. **Görsel katman:** Liquid Glass yalnız functional layer; content layer'da
   yok ve sürüm koşullu.
9. **Erişilebilirlik:** VoiceOver, Increase Contrast, Reduce Transparency,
   Reduce Motion.
10. **Pencere durumu:** minimum boyut, restore, çoklu ekran, full screen.

## Kanıt

- Ana pencere + Settings + her panel: light ve dark, minimum ve geniş boyut.
- Menü haritası ve kısayol listesi (çakışma kontrolü ile).
- VoiceOver sırası ve Full Keyboard Access notu.
- HIG referanslı ekran notları; karşılaştırma `comparison_valid: true`.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Menü | Her komut menüde, standart menüler tam |
| Klavye | Kısayol var, çakışma yok, Full Keyboard Access tam |
| Kontrol | Native; dokunma hedefi kuralı uygulanmamış |
| Görsel | Sistem font, tek accent, Glass yalnız functional layer |
| Erişilebilirlik | VoiceOver + kontrast + reduce ayarları |
| Pencere | Minimum boyut ve restore tanımlı |
| Karşılaştırma | `comparison_valid: true` |

## Anti-pattern'ler

- iOS navigation'ını Mac'e taşımak (tab bar, swipe-back).
- 44×44 pt dokunma hedefini masaüstüne uygulamak.
- Menüde olmayan komut; yalnız hover ile görünen eylem.
- Custom toolbar ve sidebar; sistem kontrolünü yeniden yazmak.
- Hardcoded renk, sabit punto, content layer'da Glass.

## Handoff

Developer'a: view/komut eşlemesi, toolbar ve menü kimlikleri, odak sırası.
Tester'a: hangi ekran ve pencere boyutunun karşılaştırılacağı.
