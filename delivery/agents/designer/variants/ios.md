# Designer — iOS

**Capability:** `platform.ios` · **Min level:** expert
**Packs:** `apple-hig`, `apple-a11y`, `apple-privacy`, `apple-asc`
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Ne zaman aktif

`platform.ios` capability'si varsa ve leaf iOS yüzeyine dokunuyorsa. Web-only
projede bu variant yüklenmez.

## Girdiler

- Leaf seal, AC, hedef cihaz ailesi (iPhone/iPad), minimum iOS sürümü.
- HIG referansı, mevcut design system, SF Symbols/asset durumu.
- Navigation modeli: tab, stack, sheet, full-screen cover.

## Yöntem

1. **Navigation:** hangi akış stack, hangi akış sheet? Geri dönüş nerede?
2. **Safe area:** notch/Dynamic Island, home indicator, klavye; hiçbir kritik
   içerik kesilmiyor mu?
3. **State matrisi:** empty/loading/error/offline, izin reddi, ödeme başarısız.
4. **Dynamic Type:** XXL ve erişilebilirlik boyutlarında taşma/kırpılma.
5. **VoiceOver:** okuma sırası, label/trait, custom action, focus kaybı.
6. **Dark mode:** semantic color; hardcoded renk yok.
7. **Etkileşim:** swipe-back, sheet detent, long-press, haptic; platform beklentisi.
8. **Privacy:** ATT/izin metni ve görsel akış; privacy label ile çelişki yok.

## Kanıt

- Screenshot: iPhone SE, iPhone 15/16 Pro Max, iPad (universal ise), portrait +
  landscape, light + dark.
- Dynamic Type XXL ve VoiceOver focus sırası notu.
- Sheet/navigation state diyagramı.
- İzin/ATT akışı (varsa).
- Handoff: SwiftUI/UIKit component eşlemesi, asset, copy.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| HIG | Navigation, kontrol ve dokunma hedefi uyumlu |
| Safe area | Kritik içerik kesilmiyor |
| Dynamic Type | XXL'de okunabilir, taşma yok |
| VoiceOver | Sıra ve label anlamlı |
| Dark mode | Semantic renk, kontrast |
| State kapsamı | Empty/error/offline/izin reddi |
| Karşılaştırma | `comparison_valid: true` |

## Anti-pattern'ler

- Android/Material desenini iOS'a taşımak.
- Sheet yerine her yerde full-screen modal.
- Dynamic Type'ı devre dışı bırakmak.
- VoiceOver'ı yalnız "label var" diye geçmek.
- iPad'i test etmeden universal demek.

## Handoff

Developer'a: SwiftUI/UIKit eşlemesi, asset, safe-area notu.
Tester'a: cihaz matrisi, Dynamic Type/VoiceOver senaryoları, izin akışı.
