---
name: platform-gate
description: >-
  Run a platform pack checklist (apple-hig, apple-a11y, web-ux, …) after the core
  gates, in the order the factory profile sets. Use when the profile lists
  platform_packs, after ui or adversarial review, or when evidence needs
  reviews.platform.
---

# platform-gate

## Input

- `pack` id (e.g. `apple-hig`)
- Profile `platform_packs` and `extra_gates` (issue `factory.profile` selects it)
- Checklist: `delivery/packs/<pack>/checklist.md`

## When

The profile's `extra_gates` defines the order (e.g. after `ui` or `adversarial`).

## Execution

1. Read the checklist.
2. Run the profile `extra_gates` command from `ecosystem.yaml` if defined;
   otherwise review-only.
3. Capture native/mobile evidence with Orca:
   - macOS native: `orca computer permissions`, `list-apps`, `get-app-state`,
     `click`, `set-value`, `paste-text`, `screenshot` (Finder/QuickLook,
     menu bar, extension flow).
   - iOS: `orca emulator list|attach|tap|type|gesture|button|rotate|kill`.
   - Android: `orca-emulator-android` (adb) skill.
   - Publish screenshots as an artifact (`orca artifacts share`) or attach the
     local path; record `orca.artifact` in evidence.
4. Return JSON pass/fail like `ui-gate`; record `reviews.platform` in evidence.

## Store packs

`apple-asc`, `google-play`: never auto-submit. Document readiness for human QA.

## Packs

Profildeki tüm `platform_packs` checklist'leri zorunludur. Kapsam dışı pack
varsa issue `decisions` kaydında gerekçeli waive gerekir.

## Done when

Her pack maddesi kanıtlandı, `reviews.platform` evidence'a JSON olarak yazıldı ve
store pack'lerinde otomatik gönderim yapılmadı.
