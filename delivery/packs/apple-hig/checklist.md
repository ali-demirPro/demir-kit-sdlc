# apple-hig pack

UI gate sonrası reviewer checklist. Blocker = gate fail. Tam denetim
prosedürü ve rubrik: `skills/hig-audit/SKILL.md` (kural kaynakları canlı
HIG referanslıdır).

- Navigation: back affordance, tab bar / nav bar HIG uyumu; `NavigationView`
  yok (`NavigationStack` / `NavigationSplitView`)
- Layout: safe area, adaptive layout; touch target ≥ 44×44 pt
- Typography: sistem font / Dynamic Type; `font(.system(size:))` hardcode yok
- Color: sistem renkleri; sabit `Color` yok; kontrast ≥ 4.5:1 (normal) /
  3:1 (large)
- Liquid Glass: yalnız functional layer (tab bar, toolbar, sidebar, nav bar,
  sheet, popover, alert); content layer'da yasak — istisna: aktive edilen
  slider/toggle transient görünüm (HIG — Materials); custom control'larda
  seyrek kullanım
- Icons: SF Symbols tercihi; custom icon gerekçeli
- Permissions: contextual istek; launch'ta değil (HIG — Accessing private
  data)
- Alerts: yalnız karar/hata; status mesajı için değil (HIG — Alerts)
- Gestures: swipe-back, destructive actions confirm
- Dark Mode: temel ekranlar her iki modda tutarlı; custom dark toggle yok

Output: JSON `{ "pass": bool, "findings": [...] }` per `ui-gate` format;
bulgular `HIG-*` (severity `critical|high|medium`, `hig_ref` zorunlu).
