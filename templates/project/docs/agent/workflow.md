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

## Seal

1. Discovery → **`work-package`** skill (`vendor/demir-kit/skills/`).
2. Label **`agent-approved`** on the issue.

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
