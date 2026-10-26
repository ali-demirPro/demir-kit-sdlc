---
name: prototype
description: >-
  Build a clickable UI contract before or during UI checkpoints — single-file HTML
  for web or documented states for mobile. Follow ecosystem design doc paths.
---

# prototype

## Web / marketing surfaces

- Prefer one HTML file under a path agreed in checkpoint (often `prototypes/` — gitignored or committed per project policy; not a work package).
- Follow `surface.design` in ecosystem.yaml.

## Mobile (Flutter / native)

- Output: state list + wire description or lightweight preview spec linked in issue comment if no HTML.
- Align with `shared.design_tokens` when set.

## Done when

User or issue references prototype URL/path in checkpoint acceptance_criteria.
