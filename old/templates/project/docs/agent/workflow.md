# Agent workflow (this repo)

## Kit bootstrap (once)

1. Full clone: `vendor/demir-kit/`
2. **`kit-setup`** — `kit.config.yaml`, this file, `AGENTS.md`
3. **`kit-envision`** — `docs/product/discovery-brief.md` → label `discovery-approved`
4. **`kit-init`** — approved brief → `ecosystem.yaml`, `docs/*`, `scripts/gate-behavior.sh`

Kit root paths: read `kit.config.yaml` → `kit.root`.

## Work packages

- **Canonical:** GitHub Issues only (`vendor/demir-kit/references/tracker-policy.md`).
- **No** `work-packages/` or `WP-*.md` in this repo.

## Hard gates (mandatory)

Read `${kit.root}/references/agent-phase-gates.md`.

| Phase | Owner | App code `src/` | `agent-approved` | Checkpoints in issue |
|-------|--------|-----------------|------------------|----------------------|
| kit-feature F0–F4 | kit-feature | **No** | **No** | Parent: **scope_triage only** |
| kit-build | kit-build **#leaf** | After seal on **#N** | **Yes** on **#N** | Full YAML on **#N** |
| Orca | coordinator | Per CP | — | Gates run here |

Before commit with app changes: `./scripts/kit-agent-guard.sh --issue N`

## Seal

1. **kit-build** on one **leaf** issue → **`work-package`** skill.
2. Label **`agent-approved`** on that issue only — not on scope parent epic.

## Orca execution (ADE)

1. Orca skills: `orchestration`, `orca-cli` (already via Orca ADE).
2. Load kit skills from `kit.root/skills/` in coordinator task specs.
3. `orca worktree create --issue <N> --name wp-<N> ...`
4. Follow `vendor/demir-kit/orchestration/README.md`.

## Human communication

All questions to the product owner: demir-kit `references/human-communication.md`.

## Repo files agents read

| Path | Purpose |
|------|---------|
| `ecosystem.yaml` | Products, surfaces, gate commands |
| `docs/architecture/` | ADRs |
| `docs/design/` | UI rules |
| `docs/agent/learnings.md` | Short notes + issue links (optional) |

## PRs

`Refs #N` / `Closes #N`
