# Gate sözleşmesi

Gate geçişi **yalnızca** doğrulanabilir çıktı ile. Agent “yeterli” diyerek geçemez (`stop-and-done-policy.md`).

## Gate sırası (checkpoint başına)

1. **behavior** — `tests_plan` cases; red-green; `ecosystem.yaml` command exit 0
2. **architect** — yalnızca `gates.architect: true`; `solution-architect` mode `output-review` (approve / revise; architect kod yazmaz)
3. **commercial** — yalnızca `gates.commercial: true`; `commercial-review` (positioning, GTM, monetization messaging)
4. **ui** — yalnızca `gates.ui: true`; scoped (`ui_scope`); dual reviewer
5. **adversarial** — dual independent reviewers → fixer → both approve
6. **platform** — `factory.profile` → `extra_gates` + `platform-gate` skill (pack checklist)
7. **human** — CP `gates.human: true`, epic `human-qa`, baseline onayları; **store submit / live pricing / ad spend** always human

`architecture_baseline` CP'leri: genelde behavior/ui/adversarial kapalı; architect `baseline` + `gates.human: true` → label `architecture-baseline-done`.

`commercial_baseline` CP'leri: `product-strategy`, `monetization-brief`, `gtm-lite` slices + `gates.human: true` → label `commercial-baseline-done`. Pack `launch-readiness` before store human QA.

Platform gate sırası profil YAML `extra_gates.after` ile core gate'lere eklenir (genelde ui/adversarial sonrası).

## behavior

- Testler `tests_plan` ile traceable.
- Prefer headless per `behavior-cli-pattern.md`.
- Geçiş: exit `0`.

## ui

- **Scope:** only regions/states in `checkpoints[].ui_scope` (kapsamlı UI karşılaştırma).
- **Two workers:** `ui-gate-visual` and `ui-gate-interaction` (same skill, different mode); **do not** load repo agent rules — only reference, prototype, design doc, screenshots.
- **INVALID:** mismatched section/state → re-capture both sides, no pass.
- Structured output: `pass`, `comparison_valid`, `findings[]` with `severity`, `location`.
- Geçiş: both reviewers `pass: true` and `comparison_valid: true`.

## commercial

- Skill: `commercial-review`.
- Reads `docs/product/positioning.md`, `gtm-lite.md`, `monetization-brief.md`, marketing/store surfaces in diff.
- Verdict: `approved` | `revise_required` (`CR-*`); max 3 rounds; label `commercial-revise`.
- See `commercial-stewardship.md`.

## architect

- Skill: `solution-architect`, mode `output-review` (or `baseline` / `tier-review` per issue).
- Reads `docs/architecture/*`, issue `architecture.review_policy`, diff vs `boundaries.md` and `cost-and-tiers.md`.
- Verdict: `approved` | `revise_required` with numbered findings (`AR-*`).
- `revise_required` → implementation worker (not architect fixer); max 3 rounds per CP, then `ask`.
- Label `architect-revise` while open; clear on `approved`.
- See `architecture-stewardship.md`.

## adversarial

- **Reviewer A** and **Reviewer B**: separate workers, separate context; read `docs/architecture/`, ADRs, lint, diff.
- Neither approves → **fixer** worker → re-run both reviewers (max 5 full rounds).
- Both `approved: true` required.
- If fix touched UI-visible code: **re-run ui gate** before `worker_done`.

## After all gates for CP

- Post `evidence-comment-template.md` on GitHub issue.
- Optional: `orca worktree set --comment`.

## İnsan

- Orca `gate-create` / `ask` — `human-communication.md`.
- Label `human-qa` → `done` or `work-package-amend`.
