---
name: health-check
description: >-
  Before Orca execution or at Run start, verify repo and runtime readiness —
  ecosystem paths, gate command dry-run, dev stack smoke. Use with work-package
  seal or coordinator Faz 0.
---

# health-check

Run başlamadan önce repo ve runtime hazırlık kontrolü.

## When

- After `agent-approved`, before first `worker-start`
- Optional during `work-package` seal if user will run immediately

## Checks (repo-relative)

1. `ecosystem.yaml` exists; listed `surfaces.*.path` directories exist.
2. For each surface in the issue: `gates.behavior` command with `{checkpoint}` replaced by `CP-HEALTH` — may fail until code exists; **command must be runnable** (binary found, script exists).
3. If UI CP in issue: note `ui_compare` (browser vs emulator); emulator list if mobile.
4. `gh auth status` OK when using GitHub tracker.
5. `orca status --json` OK when using Orca.
6. If `factory.architecture_baseline_required` and `architecture_baseline` not in `factory.waived_baselines` and issue is not `architecture_baseline`: baseline issue exists, label `architecture-baseline-done`, and `docs/architecture/overview.md` present (or blocker). If waived: brief approved + `envision.baselines_covered.architecture` or Handoff documents coverage; still warn if `overview.md` missing.
7. If `architecture.review_policy.output_review` not `off`: `docs/architecture/boundaries.md` and `cost-and-tiers.md` exist for implementation runs.
8. Greenfield: label `discovery-approved` and brief frontmatter `envision.status: approved` unless waive in `decisions` or `kit.config.yaml` `product.envision_required: false` (brownfield-only repos). `scope_triage.confirmed` + `scope-confirmed` when triage required.
9. If `factory.pilot_mode: true` → same MVO file rules as waived baselines for commercial/architecture labels (`envision-handoff.md`).
10. If `feasibility.go: false` → blocker unless waived.
11. If `commercial_baseline_required` and `commercial_baseline` not in `factory.waived_baselines`: `commercial-baseline-done`, `docs/product/positioning.md` + `gtm-lite.md` present. If waived or pilot: MVO per `envision-handoff.md`.
12. If paid surfaces: `monetization-brief.md` present.

## Output

Structured result for coordinator:

```yaml
ready: true|false
blockers: []  # human-language for ask
warnings: []
```

Do not proceed to CP-1 if `ready: false` and blockers are not waived by user via `ask`.
