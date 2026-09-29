# Architecture boundaries

## Communication rules

| From | To | Allowed | Mechanism | Notes |
|------|-----|---------|-----------|-------|
| `game.client` | `api` | yes | HTTPS REST | no direct DB |
| … | … | no | — | use shared package X |

## Shared packages

| Package | Consumers | Must not depend on |
|---------|-----------|-------------------|
| … | … | … |

## Sensitive paths (trigger architect `boundary_only` review)

- `apps/*/lib/domain/`
- `packages/shared/`
- …

## Anti-patterns (reject in output-review)

- Cross-surface import bypassing public API
- …
