---
name: design-md
description: >-
  Create or update docs/design/*.md tokens and rules before prototype/UI
  checkpoints. demir-kit design contract; not a work package file.
---

# design-md

## When

- UI checkpoints in the work package
- Bootstrap new surface in `ecosystem.yaml`

## Output

- Update or create paths referenced by `surface.design` in ecosystem.yaml
- Sections: typography, color tokens, spacing, components, motion (if any), breakpoints
- Link shared `design_tokens` package if monorepo

## Rules

- Keep concise; agents read this before `prototype` skill
- Do not duplicate full work package; link GitHub issue `#N` in commit message only

## Human

Summarize changes in plain language before user approves design PR (separate from issue mühür).
