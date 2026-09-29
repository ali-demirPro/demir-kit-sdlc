# Orca yürütme (demir-kit)

**Önce oku:** `references/product-lifecycle.md`, `references/orca-integration.md`, `references/feature-flow-dag.md`.

**Envision (packaging, no agent-approved):** `packaging-run-prompt.md`.

## Coordinator checklist

1. `orca status --json` — runtime ayakta
2. `ORCA skills get orchestration --full`
3. GitHub issue `#N` label `agent-approved`
4. `gh issue view N` → YAML (`entry`, `factory`, `reference`, `tests_plan`); load `profiles/<profile>.yaml`
5. **`health-check`** — blockers → `ask` (human-communication)
6. `orca orchestration run-create --objective "demir-kit #N" --json`
7. `orca worktree create --issue N --name wp-N ...` (recommended)
8. Her CP: behavior → architect if `gates.architect` → **commercial-review** if `gates.commercial` → **2× ui-gate** → **2× adversarial** + fixer → platform packs → evidence comment (`evidence-comment-template.md`). `architecture_baseline`: architect baseline CP’leri + human sign-off.
9. `check --wait` → `worker_done` / `ask` / `gate-resolve`
10. `human-qa` + insan dilinde `gate-create` veya `ask` → `done` veya `work-package-amend`

## Task spec şablonu

`task-spec-template.md` — her `task-create --spec` için kopyala-düzenle.

## Automation

`../templates/orchestration/automation-prompt.md` — execution coordinator prompt.

`automation-precheck-example.sh` — `agent-approved` kuyruğu için precheck örneği.

Haftalık ritim: `weekly-adaptive-loop.md`. Blocker kuralları: `references/coordinator-blockers.md`.

## Yapma

- Repo’ya `WP-*.md` veya kalıcı `checkpoints.json` commit etme (`.orchestration/` gitignore).
- Legacy `orca orchestration run` / `coordinator-start` kullanma (retired).
- Kullanıcıya teknik `ask` metni gönderme — `human-communication.md`.
