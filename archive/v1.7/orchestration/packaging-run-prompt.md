# Orca packaging run (kit-envision)

Use for **Phase 1** only — no `agent-approved` work package.

```
Objective: kit-envision <product-repo-path-or-active-workspace>

You are running demir-kit kit-envision (partner mode).

1. Read ${kit.root}/references/product-lifecycle.md, envision-handoff.md, and skills/kit-envision/SKILL.md.
2. Confirm kit.config.yaml exists; kit.root points at vendor/demir-kit.
3. Repo analysis → draft docs/product/discovery-brief.md from template.
4. Vision Q&A + council sections (≥2 architecture options). Include § Competitors and § Legal/compliance.
5. § Handoff: factory_profile_recommended, factory.waived_baselines if commercial/architecture covered in brief.
6. Human confirm → envision.status: approved, label discovery-approved on tracking issue.
7. Tell user: kit-init (materialize § Proposed ecosystem), then scope-triage (reuse § Development bets).

Do NOT write ecosystem.yaml before discovery-approved.
Do NOT seal agent-approved or start CP workers.
```

Replace `${kit.root}` from `kit.config.yaml` or `vendor/demir-kit`.
