# apple-hig pack

UI gate sonrası reviewer checklist. Blocker = gate fail.

- Navigation: back affordance, tab bar / nav bar HIG uyumu
- Layout: safe area, minimum touch targets (~44pt)
- Materials: system backgrounds, separators, hierarchy
- Typography: Dynamic Type uyumlu font stilleri
- Gestures: swipe-back, destructive actions confirm
- Dark Mode: temel ekranlar her iki modda tutarlı

Output: JSON `{ "pass": bool, "findings": [...] }` per `ui-gate` format.
