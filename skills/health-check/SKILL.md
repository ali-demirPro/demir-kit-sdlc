---
name: health-check
description: >-
  Before the first CP: verify ecosystem paths, gate command, tracker, Orca and
  baseline waivers. ready:false blocks CP-1.
---

# health-check

Full checklist: `delivery/protocol/health-check.md`. User-facing text:
`delivery/policies/human-communication.md`.

## When

After `agent-approved`, before the first `worker-start`. A pre-seal run is only a
dry run; if the seal changes, run it again before CP-1.

## Checks

1. `ecosystem.yaml` exists; every `surfaces.*.path` exists.
2. For each surface: `gates.behavior` runnable (`{checkpoint}` → `CP-HEALTH`).
3. UI CP → `gates.ui: true` and `ui_compare` defined.
4. `gh auth status` OK (GitHub tracker).
5. Orca used → `orca status --json` OK and the kit's feature probes pass:
   `orca_capabilities.py --check worktree.set` / `orchestration.worker-start` /
   (gerekliyse) `gate-create`, `computer`, `tab`, `emulator`. Sürüm karşılaştırması
   yapılmaz; eksik özellik degrade kaydı ister.
6. `orca worktree ps --json` ve `orca host list --json` çalışıyor.
7. UI web → `orca tab profile list --json`; native/mobil → `orca computer
   permissions --json` ve `orca emulator list --json`.
8. Profile `architecture_baseline_required` → `architecture-baseline-done` or recorded waive.
9. Architect review açıksa (risk high veya `gates.architect`) → `docs/architecture/boundaries.md`.
10. Greenfield → `discovery-approved` + approved brief (or waive in `decisions`).
11. `factory.pilot_mode` → MVO rules applied.
12. Feasibility blocker varsa → `blocked` + karar kaydı (`decisions` text).
13. Profile `commercial_baseline_required` → `commercial-baseline-done` + positioning/gtm.
14. Paid surfaces → `monetization-brief.md`.

Self-host (`kit-internal`): 8–10 and 12–14 are `not_applicable`; 1–7 and 11 are mandatory.

## Output

```yaml
ready: true
blockers: []
warnings: []
```

`ready: false` → `blocked` + one human-language question
([escalation.md](../../delivery/policies/escalation.md)). A waive exists only as a
`decisions` record.
