---
envision:
  status: draft  # draft | approved
  approved_at: null
  platform_decision: null  # web_continue | mobile_pivot | hybrid | unchanged | TBD
  factory_profile_recommended: null
  brief_version: 1
---

# Discovery brief

> Human-facing proposal. **`kit-init`** commits ecosystem only after `envision.status: approved` and label `discovery-approved`.

## Repo snapshot

_Agent-filled from codebase scan._

- Stack: …
- Main modules / features: …
- Docs found: …
- Tests / CI: …

## Vision (from founder)

| Topic | Answer |
|-------|--------|
| Amaç / başarı | … |
| ICP | … |
| Problem | … |
| MVP promise | … |

## Council — positioning

_Strategy layer (`product-strategy`)._

- …

## Council — platform & architecture

_Architect layer. **≥2 options** with pros/cons._

### Option A — …

- Fit: …
- Cost / time: …
- Risks: …

### Option B — …

- …

**Recommendation:** …  
**If founder overrides:** …

## Council — go-to-market & revenue

_Commercial layer (`gtm-lite`, `monetization-brief` sketch)._

- Channels: …
- Revenue hypothesis: …
- Challenge to platform (if any): …

## Competitors / alternatives

≥2 named products or category players; differentiation hook.

- …

## Legal / compliance hooks

Even if none: state “none identified” + data/PII touchpoints.

- …

## Feasibility

- Score: _/10
- Strengths: …
- Risks & mitigations: …

## Proposed ecosystem (not committed until kit-init)

```yaml
# Paste approved ecosystem fragment or full file
name: …
tracker:
  repo: owner/repo
products:
  …
```

## Proposed folder layout

```text
…
```

## Development bets (phased)

| Phase | Bet | Value | Effort | Decision |
|-------|-----|-------|--------|----------|
| 1 | … | … | S/M/L | keep |
| 2 | … | … | … | defer |

## Handoff to SDLC

- Recommended profile: `…`
- Next: `kit-init` (materialize per `references/envision-handoff.md`) → `scope-triage` → `factory-routing`
- **Baseline epic skip** (`yes` = add to `factory.waived_baselines` on seal — see `envision-handoff.md`):
  - `commercial_covered`: yes | no
  - `architecture_covered`: yes | no
- `split_files`: positioning | gtm-lite | monetization-brief | architecture-overview | (none)
- `envision.baselines_covered`: `{ commercial: true|false, architecture: true|false }` (must match `*_covered`)
- Envision waive (emergency only): issue `decisions` + coordinator `ask` — not default

## Approval log

| Date | Who | Note |
|------|-----|------|
| … | founder | discovery-approved |
