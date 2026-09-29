# Capability activation (selective council)

VB **Council** → demir-kit **skills + packs**, persona roleplay yok.

## Profile defaults

Each `profiles/*.yaml` may define:

```yaml
optional_capabilities:
  - id: design-md
    when: gates.ui or custom design
  - id: prototype
    when: reference.kind prototype_url
  - id: gtm-lite
    when: marketing.site or store_release in scope (default on greenfield profiles)

default_skips:
  - id: heavy-gtm
    reason: Long-form marketing plan; commercial_baseline + gtm-lite instead
  - id: help-center-pack
    reason: Support-heavy; defer until MAU threshold
```

## Merge at seal (`work-package`)

1. Start from profile `required_skills` → `factory.activated_skills`.
2. Add optional capabilities when `when` matches issue (surfaces, gates, discovery).
3. Append `default_skips` to `factory.skipped_capabilities` unless user override in `decisions`.
4. Compliance: if `discovery.audience` child-related or risk mentions COPPA/GDPR → activate privacy packs + `solution-architect` decision; do not skip `apple-privacy` on iOS kids apps.

## Issue comment snapshot

On seal, optional comment `## Activated capabilities` listing activated vs skipped (human-readable one line each).

## Skills catalog (activation targets)

| id | Skill / pack |
|----|----------------|
| kit-envision | kit-envision (greenfield / brownfield discover) |
| discovery-intake | **legacy alias** — use kit-envision |
| scope-triage | scope-triage |
| solution-architect | solution-architect |
| design-md | design-md |
| prototype | prototype |
| platform-gate | platform-gate + platform_packs |
| test-plan | test-plan |
| learnings | learnings |
| product-strategy | product-strategy |
| monetization-brief | monetization-brief |
| gtm-lite | gtm-lite |
| commercial-review | commercial-review |
