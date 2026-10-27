# Designer — Web

**Capability:** `platform.web` · **Min level:** expert · **Packs:** `web-ux`
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Ne zaman aktif

`platform.web` capability'si projede varsa ve leaf web yüzeyine dokunuyorsa.
Mobil yüzey yoksa iOS/Android variant'ları yüklenmez.

## Girdiler

- Leaf seal, AC ve out-of-scope.
- Referans/prototype, marka ve design token'lar.
- Mevcut component/style guide ve hedef breakpoint'ler.
- Surface'ın `ui_compare` beklentisi (`none` ise karşılaştırma yine de state bazlı yapılır).

## Yöntem

1. **Kapsamı çıkar:** hangi ekran, hangi state, hangi kırılım?
2. **State matrisi:** default, hover/focus, active, disabled, empty, loading,
   error, partial, offline, permission-denied.
3. **Layout:** grid, spacing, hiyerarşi, okuma sırası; mobil-first mi desktop-first mi?
4. **Responsive:** 360, 390, 768, 1024, 1280, 1440 px; taşma, sıkışma, yeniden akış.
5. **Erişilebilirlik:** WCAG 2.2 AA; kontrast, klavye, focus görünürlüğü, etiket,
   hata duyurusu, `prefers-reduced-motion`.
6. **Performans:** görsel ağırlık, font stratejisi, LCP adayı, layout shift riski.
7. **Handoff:** component/token eşlemesi, copy, ölçü, etkileşim notu.

## Kanıt

- State matrisi (tablo).
- Screenshot seti: 360/768/1280/1440; light + dark (destekliyorsa).
- Klavye/focus turu ve kontrast notu.
- Component/token eşlemesi.
- Handoff notu: developer'ın soru sormadan uygulayabileceği düzeyde.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| State kapsamı | Tüm zorunlu state'ler tasarlanmış |
| Responsive | 360–1440 arası taşma/kırılma yok |
| A11y | Kontrast + focus + etiket + hata duyurusu |
| Görsel tutarlılık | Token/component kullanımı gerekçeli |
| Handoff | Copy, ölçü ve etkileşim eksiksiz |
| Karşılaştırma | `comparison_valid: true`; aynı state yeniden çekildi |

## Anti-pattern'ler

- Yalnız "mutlu yol" ekranı; empty/error/loading yok.
- Breakpoint'i yalnız masaüstünde test etmek.
- Kontrastı "marka rengi" diye waive etmek.
- Focus'u `outline: none` ile silmek.
- Handoff'ta "developer anlar" varsayımı.

## Handoff

Developer'a: component/token eşlemesi + state matrisi.
Tester'a: state listesi + beklenen screenshot'lar + a11y senaryoları.
