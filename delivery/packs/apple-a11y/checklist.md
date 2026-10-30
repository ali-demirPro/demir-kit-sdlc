# apple-a11y pack

Behavior veya dedicated CP sonrası. Derin tarama prosedürü:
`skills/hig-audit/SKILL.md` accessibility bölümü.

- VoiceOver: primary flow okunabilir; anlamlı label + trait + hint; boş
  `.accessibilityLabel` blocker
- Dynamic Type: largest size kırılmadan; sistem font scale destekli
- Contrast: metin/arka plan ≥ 4.5:1 (normal) / 3:1 (large) (WCAG AA,
  reviewer)
- Differentiate Without Color: anlam renk tek başına taşınmıyor
- Reduce Motion: animasyon alternatifi veya respect
- Keyboard / Switch Control: odak sırası ve donanım klavye hazırlığı
  (macOS/iPadOS)
- Touch target ≥ 44×44 pt
- XCTest accessibility audit exit 0 (ürün script'i ecosystem'te tanımlı)
