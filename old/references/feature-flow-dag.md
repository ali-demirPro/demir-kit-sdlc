# Feature flow → Orca primitives (demir-kit 1.7.1)

Pre-execution (no `agent-approved`): `product-lifecycle.md` — `kit-envision` packaging run (`packaging-run-prompt.md`).

## Faz 0 — Hydrate

1. `run-create` — objective `demir-kit #N`
2. `gh issue view` → parse YAML (`entry`, `factory`, `reference`, `tests_plan`, `checkpoints`, `factory.waived_baselines`, `factory.pilot_mode`)
3. Load `profiles/<factory.profile>.yaml` for `extra_gates`
4. If `entry.kind: architecture_baseline` → Run uses **`solution-architect`** only (no feature behavior until docs CP done)
5. **`health-check`** — envision/scope/baseline/waive rules (`envision-handoff.md`)
6. `worktree create --issue N` (recommended)
7. `checkpoint-planner` refine-only if `checkpoints_preapproved`
8. `task-create` per CP

## Faz 1 — Per checkpoint (order = topological)

| Step | Workers | Skill |
|------|---------|--------|
| Behavior | 1 | `behavior-gate` (tests_plan cases) |
| Architect | 1 | `solution-architect` `output-review` if `gates.architect` |
| Commercial | 1 | `commercial-review` if `gates.commercial` |
| UI | 2 parallel | `ui-gate` visual + interaction |
| Adversarial | 2 parallel → fixer loop | `adversarial-review` |
| Platform | per profile `extra_gates` | `platform-gate` |
| Human CP | coordinator | `gates.human` or baseline sign-off |
| Regression | conditional | behavior cmd; ui if UI files changed |
| Evidence | coordinator | `evidence-comment-template.md` → `gh issue comment` |

## Faz 2 — Epic

Parent blocked until children done + evidence on each.

## Faz 3 — Human QA

`human-qa` label; `gate-create` / `ask`; `done` or `work-package-amend`.

## Docs

- `product-lifecycle.md`, `envision-handoff.md`, `gate-contract.md`, `stop-and-done-policy.md`
