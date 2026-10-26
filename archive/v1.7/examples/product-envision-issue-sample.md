## Summary

Product envision — direction lock before ecosystem commit. Not executable; no agent-approved.

## Human checklist

- [ ] Platform recommendation read (including alternatives)
- [ ] Development bets phase 1 acceptable
- [ ] Approve → label discovery-approved

```yaml demir-kit
demir_kit_version: "1"
package_version: 1
mode: extend
entry:
  kind: product_envision
  summary: Yön ve discovery brief onayı.
factory:
  profile: web-product
  product_class: web-app
  stacks: [next]
  quality_tier: standard
  distribution: [web-only]
  platform_packs: [web-ux]
  store_ops_in_scope: false
envision:
  status: draft
  brief_path: docs/product/discovery-brief.md
  platform_decision: tbd
  factory_profile_recommended: web-product
intent: Facilitate kit-envision council and discovery-brief approval.
products: [web]
surfaces: [web.app]
reference:
  kind: github_paths
  summary: Repo root and docs for envision scan.
  paths:
    - package.json
    - src/
    - docs/
acceptance_criteria:
  - discovery-brief.md complete with council sections
  - User label discovery-approved
out_of_scope:
  - Feature implementation
  - ecosystem.yaml commit before approval
decisions: []
dependencies: []
tests_plan:
  - checkpoint_id: CP-ENV-1
    cases:
      - name: brief approved
        expectation: envision.status approved in brief frontmatter
        edge: false
checkpoints_preapproved: true
checkpoints:
  - id: CP-ENV-1
    title: Envision sign-off
    order: 1
    depends_on: []
    surfaces: [web.app]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, commercial: false, human: true }
    acceptance_criteria:
      - discovery-approved
```
