---
name: kit-upgrade
description: >-
  Product owner command — sync vendored demir-kit from upstream (local clone or
  git). Updates kit.version and optionally refreshes Orca owner skills.
---

# kit-upgrade

Apply `human-communication.md` for all user-facing messages.

**Hard gates:** `${kit.root}/references/agent-phase-gates.md` (G1 — no app paths).

## STOP

- **Only** `${kit.root}/`, `kit.config.yaml` `kit.version`, Orca skill refresh.
- **Never** `src/`, `docs/product/discovery-brief.md`, issue seal, or implementation.

Run `kit-agent-guard.sh` after sync — must pass (no app diff).

## When the owner says "kit-upgrade"

Sync the product repo’s vendored kit (`kit.config.yaml` → `kit.root`, usually `demir-kit/`) from upstream without touching app code or `docs/product/`.

### 1 — Preconditions

- Working directory: **product repo root** (`kit.config.yaml` present).
- Read `kit.config.yaml`:
  - `kit.root`
  - `kit.upstream.local` (preferred if directory exists)
  - `kit.upstream.git` (fallback clone)
  - `kit.overlay` (optional; applied after sync)

### 2 — Resolve source (in order)

1. Owner passed path → use `--from`.
2. Else `kit.upstream.local` → if relative, resolve from repo root; if `.git`, run `git pull` first.
3. Else `kit.upstream.git` → shallow clone to temp (script handles).
4. If none configured → ask owner for path or git URL once; suggest adding `upstream` to `kit.config.yaml`.

### 3 — Run upgrade script

```bash
./scripts/kit-upgrade.sh --dry-run
```

Summarize in **Turkish** (short): old VERSION → new VERSION, whether `--delete` will remove vendor files, overlay if any.

On owner confirm (or explicit “güncelle” without dry-run if they already asked to upgrade):

```bash
./scripts/kit-upgrade.sh
```

Flags when needed:

| Flag | Use |
|------|-----|
| `--dry-run` | Preview only |
| `--no-delete` | Keep files removed upstream (safer, can leave stale files) |
| `--skip-orca` | Skip `install-orca-user-skills.sh` |
| `--from PATH` | Override local upstream |
| `--git URL` | Override git upstream |

Script path (after vendor exists): `${kit.root}/tools/kit-upgrade.sh` via product `scripts/kit-upgrade.sh` wrapper.

### 4 — After sync

- Confirm `kit.config.yaml` `kit.version` matches `${kit.root}/VERSION`.
- Mention `git diff --stat` on `demir-kit/` if repo is git.
- **Do not commit** unless owner asks.
- **Do not** edit `docs/product/`, `src/`, or sealed issues.

### 5 — If vendor lacks `tools/kit-upgrade.sh` (bootstrap)

One-time:

```bash
rsync -a --delete <upstream>/ ./demir-kit/
chmod +x demir-kit/tools/kit-upgrade.sh scripts/kit-upgrade.sh
```

Then normal `kit-upgrade` flow.

## Do not

- Change discovery brief or product direction as part of kit-upgrade.
- Bulk-install internal gate skills into Orca (only `install-orca-user-skills.sh` owner set).

## Complete

Vendored kit matches upstream VERSION; owner informed of Orca refresh if run.
