# Kit bootstrap layout (product repo)

After **`kit-setup`** → **`kit-envision`** (`discovery-approved`) → **`kit-init`** (see **`envision-handoff.md`**).

```text
<product-repo>/
  kit.config.yaml          # kit.root → vendor/demir-kit
  ecosystem.yaml           # surfaces, gate commands
  AGENTS.md                # optional — Orca ADE / agents pointer
  vendor/
    demir-kit/             # full clone (skills, references, profiles, …)
  docs/
    product/               # discovery-brief.md (envision), context, positioning, …
    architecture/          # overview, boundaries, ADRs
    design/                # design-md output
    agent/
      workflow.md          # kit-setup
      learnings.md         # optional
  scripts/
    gate-behavior.sh       # kit-init stub — replace per stack
  orchestration/           # optional pointers only (prefer vendor/demir-kit/orchestration)
  .orchestration/          # gitignored — Orca ephemeral
  apps/ …                  # your code (paths match ecosystem.yaml)
```

## kit.config.yaml

See `templates/project/kit.config.yaml`.

## Updating kit

Bump `vendor/demir-kit` (pull/submodule); re-run **`kit-setup`** only if paths or Orca integration changed.
