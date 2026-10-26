# Agents (this repository)

## Kit

- **Root:** `vendor/demir-kit` (see `kit.config.yaml`)
- **Bootstrap:** `kit-setup` → `kit-init` skills under `${kit.root}/skills/`
- **Protocol:** demir-kit `VERSION` in kit root; work packages = GitHub issues only

## Orca ADE

Execution via Orca (`orchestration`, `orca-cli`). Providers (Cursor, OpenCode, Cline) run **under Orca** — load kit skills from `vendor/demir-kit/skills/`, not per-IDE copies.

## Must read before packaging

`${kit.root}/skills/kit/SKILL.md`

## Must read before CP execution

`${kit.root}/references/gate-contract.md`, `${kit.root}/orchestration/README.md`

## Repo

| Path | Purpose |
|------|---------|
| `ecosystem.yaml` | Surfaces and behavior gate commands |
| `docs/product/` | Discovery & commercial artifacts |
| `docs/architecture/` | Architect baseline |
| `docs/design/` | UI design-md |

Human language: `${kit.root}/references/human-communication.md`
