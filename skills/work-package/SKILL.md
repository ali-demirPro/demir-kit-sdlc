---
name: work-package
description: >-
  Seal a v2 leaf: demir-kit YAML, AC ↔ tests_plan mapping, risk level, then
  agent-approved. No seal, no source changes.
---

# work-package

Read first: `delivery/protocol/seal.md`, `delivery/CONTRACT.md`,
`delivery/schemas/leaf.schema.json`. User-facing text:
`delivery/policies/human-communication.md`.

## Entry check (block on fail)

1. Issue is a **leaf**, not a scope-only epic.
2. Parent epic has `scope-confirmed`.
3. Risk level declared (`low` / `medium` / `high` / `critical`).
4. No source edit before seal (`delivery/scripts/guard.sh`).

## Non-negotiables

- No `WP-*.md`, `docs/work-packages/`, or committed checkpoint JSON.
- One leaf per issue; never seal an epic that has children.
- Every `AC-n` has at least one `T-n` case; every CP has a `tests_plan` entry.
- `demir_kit_version: "2"`; `gates.behavior: true` on every CP.

## Steps

1. Fill the `demir-kit` YAML block.
2. Run `test-plan`; map cases to AC ids.
3. Choose risk; `registry.yaml` globs may auto-escalate it.
4. Validate: `./delivery/scripts/doctor.sh --body /tmp/leaf.md`.
5. Update the issue body; add `agent-approved`, remove `intake`.
6. Next: `health-check`, then `delivery/protocol/execution.md`.

## Template

```yaml demir-kit
demir_kit_version: "2"
package_version: 2
mode: extend
epic: 12
entry: { kind: feature }
factory: { profile: kit-internal }
intent: "Tek paragraf, ne ve neden."
surfaces: [kit.docs]
reference:
  kind: github_paths
  summary: "Ne ile doğrulanacak."
  paths: [delivery/CONTRACT.md]
acceptance_criteria:
  - { id: AC-1, text: "Test edilebilir sonuç." }
out_of_scope: ["Bu leaf'in kapsamı dışındaki iş"]
risk: { level: low, reasons: ["Doküman değişikliği"] }
tests_plan:
  - checkpoint_id: CP-1
    cases:
      - { id: T-1, ac: AC-1, text: "Doğrulama adımı." }
checkpoints:
  - id: CP-1
    title: Kısa başlık
    gates:
      behavior: true
      architect: false
      commercial: false
      ui: false
      human: false
```

## Failure modes

| Hata | Sonuç |
|------|-------|
| AC testsiz | `doctor` fail |
| `behavior: false` | şema fail |
| Risk düşük yazıldı | `guard.sh` glob ile bloklar |
| Epic mühürlendi | contract ihlali |
