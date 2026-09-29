---
name: kit-setup
description: >-
  Wire kit.config.yaml, agent workflow, Orca checks, and brownfield envision (Phase 2).
  Run once per product repo. kit.root may be demir-kit/ or vendor/demir-kit/.
---

# kit-setup

Apply `human-communication.md` for user messages.

## Goals

1. Connect product repo to kit root (`kit.config.yaml`).
2. Verify Orca platform skills (`orchestration`, `orca-cli`).
3. Write or merge `docs/agent/workflow.md`; optional `AGENTS.md` demir-kit pointer.
4. Point `orchestration/README.md` at `${kit.root}/orchestration/README.md` (no full kit copy unless user asks).
5. **Phase 2 (same bootstrap):** brownfield **kit-envision** lite — not a separate owner habit after setup.

## Steps

### 1 — Verify kit root

- Path: `${kit.root}/VERSION` exists (e.g. `demir-kit/VERSION` or `vendor/demir-kit/VERSION`).
- Write `kit.config.yaml` at **product repo root** from `templates/project/kit.config.yaml`:
  - `kit.root` → actual folder name
  - `kit.version` from VERSION file
  - `tracker.repo` (`gh repo view --json nameWithOwner` or ask user)

### 2 — Orca (ADE)

Confirm user has:

- `orchestration`
- `orca-cli`

Optional product `orchestration/README.md` → pointer to `${kit.root}/orchestration/README.md`.

### 3 — Orca user skills (owner only)

**Install only these** from kit root (optional product helper: `templates/project/scripts/install-orca-user-skills.sh` → repo `scripts/`):

| Skill | Role |
|-------|------|
| `kit-feature` | → scope-triage |
| `kit-build` | → work-package (+ autonomous kit-init) |
| `kit-build-change` | → work-package-amend |
| `kit-upgrade` | → sync vendored kit from `kit.upstream` |

```bash
npx skills add file://$PWD/demir-kit --skill kit-feature
npx skills add file://$PWD/demir-kit --skill kit-build
npx skills add file://$PWD/demir-kit --skill kit-build-change
npx skills add file://$PWD/demir-kit --skill kit-upgrade
```

**Do not** bulk-install all kit skills. Coordinators read internal skills from disk:

`Read ${kit.root}/skills/<name>/SKILL.md` (gates, test-plan, health-check, architect, kit-init, …).

**kit-init** is **not** an owner Orca skill — runs automatically on first **kit-build** when `ecosystem.yaml` is missing.

### 4 — Agent docs

- Merge `templates/project/docs/agent/workflow.md` → `docs/agent/workflow.md`.
- Optional: extend `AGENTS.md` with demir-kit section (commands, paths, doc staleness).

### 5 — GitHub labels (optional)

Import from `${kit.root}/templates/github/labels.json` if missing (`discovery-approved`, `agent-approved`, `scope-confirmed`, …).

### 6 — .gitignore

Append `templates/project/.gitignore.append` if `.orchestration/` not ignored.

## Phase 2 — Envision (brownfield, end of kit-setup)

After wiring, run **`kit-envision`** lite (read `${kit.root}/skills/kit-envision/SKILL.md`):

- `docs/product/discovery-brief.md` + `docs/product/context.md`
- Label **`discovery-approved`** on tracking issue
- Set `envision.status: approved` in brief front matter when owner agrees

Full greenfield council only when owner explicitly requests it.

**Do not** tell owner to run kit-envision as a separate recurring step if setup just finished Phase 2.

## Shell alternative

```bash
export KIT_ROOT=demir-kit   # or vendor/demir-kit
"$KIT_ROOT/tools/kit-setup.sh" --repo owner/name
```

## After setup

Day-to-day: **kit-feature** → **kit-build** → Orca. **kit-build-change** when sealed scope shifts.

## Complete

`kit.config.yaml` committed; `docs/agent/workflow.md` present; envision approved or `envision_required` documented; Orca platform skills OK.
