# Designer — Android

**Capability:** `platform.android` · **Min level:** expert
**Packs:** `google-play`
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Ne zaman aktif

`platform.android` capability'si varsa ve leaf Android yüzeyine dokunuyorsa.
Flutter projesinde `flutter-multi` parity pack'i ayrıca devreye girer.

## Girdiler

- Leaf seal, AC, minimum SDK, hedef cihazlar (phone/tablet/foldable).
- Material 3 referansı, mevcut Compose/View component'leri.
- Navigation modeli: bottom bar, nav drawer, predictive back.

## Yöntem

1. **Navigation:** top-level destination'lar, back stack, predictive back.
2. **Edge-to-edge:** system bar insets, gesture navigation, klavye.
3. **State matrisi:** empty/loading/error/offline, izin reddi, düşük pil.
4. **Window size classes:** compact/medium/expanded; tablet/foldable yeniden akış.
5. **TalkBack:** okuma sırası, content description, canlı bölge, focus.
6. **Font scale:** 1.3 ve 2.0'da taşma/kırpılma.
7. **Material 3:** dynamic color, tonal elevation, shape scale; marka ile çatışma.
8. **Play policy:** izin gerekçesi, veri güvenliği, yaş/İçerik derecelendirmesi.

## Kanıt

- Screenshot: phone, tablet/foldable, font scale 1.3/2.0, light + dark.
- Back/predictive-back state diyagramı.
- TalkBack focus sırası notu.
- İzin akışı ve Play data safety notu.
- Handoff: Compose/View eşlemesi, dimens, copy.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Material 3 | Kontrol, shape, tonal hiyerarşi tutarlı |
| Edge-to-edge | Inset/klavye altında kritik içerik yok |
| Back | Predictive back ve geri dönüş doğru |
| TalkBack | Sıra ve açıklama anlamlı |
| Font scale | 2.0'da okunabilir |
| State kapsamı | Empty/error/offline/izin reddi |
| Karşılaştırma | `comparison_valid: true` |

## Anti-pattern'ler

- iOS tab bar'ını Android'e kopyalamak.
- `adjustResize`/inset'i yok saymak.
- TalkBack'i yalnız "içerik var" diye geçmek.
- Foldable/tabletı test etmeden desteklemek.
- Play izin metnini ürün metninden bağımsız yazmak.

## Handoff

Developer'a: Compose/View eşlemesi, inset/dimens, back davranışı.
Tester'a: API level matrisi, TalkBack/font scale, Play pre-launch.
