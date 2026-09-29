---
name: kit-build-change
description: >-
  Product owner command — amend a sealed work package after scope change (alias
  for work-package-amend).
---

# kit-build-change

**Canonical skill:** `${kit.root}/skills/work-package-amend/SKILL.md`  
**Hard gates:** `${kit.root}/references/agent-phase-gates.md`

Apply `human-communication.md`.

## Preconditions (block if fail)

- Issue already has **`agent-approved`** and sealed `demir-kit` YAML.
- Owner names issue **#N** explicitly.

## When the owner says "kit-build-change"

- Run **work-package-amend** from the canonical skill.
- Bump `package_version`, audit comment on issue, human-language summary.
- App changes only within amended scope; run `kit-agent-guard.sh --issue N` before commit.

## Do not

- Use for first seal — use **kit-build**.
- Use during **kit-feature** (scope-only) on parent epic.
