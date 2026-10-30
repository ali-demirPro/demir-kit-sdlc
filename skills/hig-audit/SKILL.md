---
name: hig-audit
description: >-
  Apple design audit for iOS/iPadOS/macOS (SwiftUI first) against the live
  Human Interface Guidelines. Repo discovery, cited non-negotiables, HIG-*
  findings with concrete fixes; optional Apple Design Awards and anti-slop lens.
---

# hig-audit

Apple platform design reviewer. Audits an iOS / iPadOS / macOS codebase
(SwiftUI first, UIKit/AppKit second) against the current Apple Human
Interface Guidelines. Official source:
https://developer.apple.com/design/human-interface-guidelines

## Rules of engagement

1. **No invented HIG rules.** Every finding cites an official HIG page and
   follows its wording. A rule that cannot be cited is a `suggestion`,
   never `critical`.
2. **Fetch HIG live.** HIG pages have a JS-free markdown endpoint:
   `https://developer.apple.com/design/human-interface-guidelines/<page>.md`
   (e.g. `materials`, `color`, `typography`, `layout`, `icons`,
   `accessibility`, `alerts`, `accessing-private-data`, `tab-bars`,
   `sidebars`, `navigation-bars`). Verify wording before quoting.
3. **Target era comes from the project** — deployment targets and
   `#if os(...)` usage. Never hardcode an OS version; Liquid Glass evolves
   per release (transparency control, Reduce Transparency / Increase
   Contrast adaptation, sidebar refinements) and its guidance changes.
4. **Declared design system is binding** (P1 — `kit.config.yaml
   product.priorities.design_system`, see
   `delivery/policies/project-priorities.md`). Measure compliance with the
   project's own system; never invent or propose a new one.
5. **Diagnosis + prioritized fixes.** No full redesign unless explicitly
   asked. Give `Dosya:Satır` references and concrete code suggestions.

## Phase 1 — Repo discovery (read, never guess)

- App entry point, Scene, root navigation (TabView, NavigationStack,
  NavigationSplitView, sidebar).
- Design tokens: Color, Font, Spacing, Radius, Material, Theme files.
- Custom components vs system components.
- Platform conditionals (`#if os(iOS)`, `#if os(macOS)`, …).
- Accessibility modifiers (`.accessibilityLabel`, `.accessibilityHint`,
  `.accessibilityAddTraits`, Dynamic Type).
- Liquid Glass / material usage (`.glassEffect`, materials, tinted glass).
- SF Symbols usage vs custom image assets.

## Phase 2 — HIG evaluation

### Design principles

Clarity, Deference, Depth; inclusive design; platform context preserved
across devices.

### Foundations

- **Layout & spacing** — safe areas, padding consistency, adaptive layout,
  `GeometryReader` overuse.
- **Typography** — system fonts, Dynamic Type, hierarchy.
- **Color & materials** — system colors vs hardcoded values, Liquid Glass
  adoption + legibility, vibrancy, contrast.
- **Icons** — SF Symbols preferred; correct scale/weight/renderingMode.
- **Motion** — `withAnimation`, Reduce Motion respected.

### Components

- System components used correctly (Button styles, List, Form, Toolbar,
  Sheet, Alert, `searchable`, …).
- Custom components derive from one source; flag one-offs.
- Tab bar / sidebar adaptive behavior on iPadOS and macOS.
- Navigation patterns: hierarchical vs flat, modality, feedback.

### Platform differences

- **iOS** — bottom tab bar + Liquid Glass, compact, touch-first.
- **iPadOS** — NavigationSplitView / adaptable sidebar, multitasking,
  pointer support.
- **macOS** — menu bar, toolbar, window management, keyboard focus, higher
  density, sidebar refinements.
- Flag every missing platform adaptation.

### Accessibility (mandatory deep scan)

VoiceOver labels and traits · Dynamic Type · Contrast + Differentiate
Without Color · Reduce Motion · Keyboard / Switch Control readiness.

### Design system consistency

Single source for color, radius, spacing, elevation, material · component
variants composed correctly · consistent cross-screen and cross-platform
visual language · dark / light / tinted Liquid Glass behavior present in
code.

## Non-negotiables (violation = `critical`)

| Rule | Source |
|------|--------|
| Touch target ≥ 44×44 pt | HIG — Layout / Accessibility |
| Text contrast ≥ 4.5:1 (normal), ≥ 3:1 (large) | WCAG 2.x AA via HIG — Accessibility |
| Dynamic Type supported (system font scale or `.dynamicTypeSize`) | HIG — Typography / Accessibility |
| **Liquid Glass only in the functional layer** (tab bar, toolbar, sidebar, navigation bar, sheet, popover, alert). Forbidden in the content layer (cards, list rows, backgrounds, media) — **exception**: a transient interactive control in the content layer (slider, toggle) takes on a Liquid Glass appearance while active. On custom controls use sparingly. | HIG — Materials |
| SF Symbols preferred; custom icon only when genuinely necessary | HIG — Icons / SF Symbols |
| Permission requests contextual, never at launch | HIG — Accessing private data |
| Alert only for a decision or an error, never for status | HIG — Alerts |

## Common failure modes (scan explicitly)

- Hardcoded `Color`, `padding`, `font(.system(size:))` values.
- `NavigationView` (deprecated → `NavigationStack` / `NavigationSplitView`).
- Custom dark mode toggle overriding the system setting.
- `.destructive` role on a primary button.
- Touch target below 44 pt.
- Missing or empty `.accessibilityLabel`.
- Liquid Glass in content containers (check the slider/toggle exception
  first).
- Onboarding without a skip button or forced permissions.
- Missing empty / error / loading states.
- Layout without platform conditionals that breaks on iPadOS/macOS.

## Severity

- `critical` — non-negotiable violation, accessibility blocker, platform break.
- `high` — design system inconsistency, wrong component usage, Liquid Glass
  layer error.
- `medium` — polish, craft, delight, small inconsistencies.

## Priority order (action list)

1. Accessibility
2. Design tokens / system consistency
3. Navigation & platform adaptation
4. Liquid Glass correctness
5. Polish / delight / craft

## Output

Machine format (evidence, `ui-gate` style):

```json
{
  "pass": false,
  "findings": [
    {
      "id": "HIG-1",
      "severity": "critical",
      "file": "path/File.swift",
      "line": 42,
      "hig_ref": "https://developer.apple.com/design/human-interface-guidelines/materials",
      "fix": "concrete code change"
    }
  ]
}
```

Human report — Turkish, fixed structure:

```
Özet — 1-3 cümle genel değerlendirme
Kritik sorunlar — [Dosya:Satır] [Sorun] → [HIG referansı] → [somut düzeltme]
Yüksek öncelikli iyileştirmeler
Orta seviye iyileştirmeler
Güçlü yönler — kodda gerçekten iyi yapılmış noktalar
Tasarım sistemi tutarlılığı — token dosyaları, component library, cross-platform notlar
Öncelikli aksiyon listesi — en yüksek etki / en kolay düzeltme sırasıyla
```

### Optional lens (`--awards`)

Apple Design Awards categories scored `award-ready` / `strong` /
`needs work`: Delight and Fun · Inclusivity · Innovation · Interaction ·
Social Impact (if applicable) · Visuals and Graphics.

Anti-slop checks: is the screen distinguishable from Apple's own Settings
app? does every element justify its existence? generic template feel (flat
gray cards, uniform `.body` font, no depth)?

## Evidence

Attach the JSON + Turkish report to the leaf evidence as
`reviews.hig_audit`. When dispatched by `platform-gate`, the same JSON is
the pack checklist output (`reviews.platform`).