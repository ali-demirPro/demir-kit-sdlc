---
name: test-plan
description: >-
  Required before seal: fill tests_plan per checkpoint and map every acceptance
  criterion to at least one case. Use when sealing a leaf, when doctor reports an
  uncovered AC, or when an amend adds cases.
---

# test-plan

## When

During seal (mandatory), before `agent-approved`. A later amend may add cases but
must not delete coverage without a decision record.

## Input

- `reference` block (paths, running app, prototype)
- `acceptance_criteria` (`AC-n`) and `checkpoints` (`CP-n`)

## Output

Issue YAML `tests_plan[]` in the v2 shape:

```yaml
tests_plan:
  - checkpoint_id: CP-1
    cases:
      - { id: T-1, ac: AC-1, text: "second claim same day rejected", check: unit }
      - { id: T-2, ac: AC-2, text: "happy path returns 200", check: gate }
```

`package_version: 4` ve sonrası her case'te `check` ister:

| Tür | Ne kanıtlar | Zorunlu koşul |
|-----|-------------|---------------|
| `gate` | ecosystem surface gate komutu (exit 0) | — |
| `unit` | test suite | — |
| `snap` | ekran görüntüsü karşılaştırması | CP `gates.ui: true` |
| `manual` | insan doğrulaması | CP `gates.human: true` |
| `doc` | doküman/sözleşme kontrolü (`doctor`) | — |

Seçim kuralı: en ucuz yeterli tür. Görünür bir değişiklik `snap`, insan
yargısı gerektiren tat/kabul `manual`, kural ve hesap `unit`, akış `gate`,
doküman `doc`.

- Every `AC-n` is covered by at least one case.
- Every CP with `gates.behavior: true` has at least one case.
- Validate with `./delivery/scripts/doctor.sh --body FILE`.

## Style

- User-perspective integration checks where possible.
- Edge cases beyond the happy path.
- Doc-only leaves may use a deterministic check (e.g. `doctor.sh`).

## Storage

Only the GitHub issue body/comment. Never commit a test-plan file.

## Done when

Her `AC-n` en az bir `T-n` case'iyle eşlendi, her behavior CP'sinin case'i var ve
`doctor.sh --body` sıfır hata veriyor.
