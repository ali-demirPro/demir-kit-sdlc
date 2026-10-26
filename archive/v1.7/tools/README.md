# Kit tools

Run from **product repo root** after `vendor/demir-kit` clone.

| Script | Purpose |
|--------|---------|
| `kit-setup.sh` | `kit.config.yaml`, `docs/agent/workflow.md`, `AGENTS.md`, `.gitignore` |
| `kit-init.sh` | After **discovery-approved** → ecosystem, layout dirs, stubs; agent MVO per `references/envision-handoff.md` |
| `kit-upgrade.sh` | Sync vendored `${kit.root}` from `kit.upstream.local` or `kit.upstream.git` |
| `resolve-skills-source.sh` | Pick git URL or local git clone for `npx skills add` (vendor without `.git` → upstream) |
| `kit-agent-guard.sh` | Block app path diffs without `agent-approved` on `--issue N` (`agent-phase-gates.md` G1) |

```bash
export KIT_ROOT=vendor/demir-kit
chmod +x "$KIT_ROOT/tools/"*.sh
"$KIT_ROOT/tools/kit-setup.sh" --repo owner/name
# kit-envision (agent) → discovery-approved
"$KIT_ROOT/tools/kit-init.sh" --repo owner/name --profile web-product
```

Agent skills: `kit-setup`, **`kit-envision`**, `kit-init`.
