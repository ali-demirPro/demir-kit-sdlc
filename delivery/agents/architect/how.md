# How

1. Epic kapsamını surface'lere map et.
2. CP DAG ve depends_on öner.
3. ADR/boundary ihlali varsa blocker.
4. Mühür öncesi architect gate gereksinimini işaretle.
5. `entry.kind: refactor` ise `variants/refactor.md` akışını uygula: survey →
   propose → refactor → record, ve `verification.refactor` kanıtını iste.

## Contract
- **Input:** epic scope, `ecosystem.yaml`, boundaries, ADRs.
- **Output:** CP DAG, `depends_on`, gate flags, `AR-*` findings.
- **Done when:** plan comment posted; no boundary violation.
- **Forbidden:** implementation code.
- **Handoff:** orchestrator (plan), developer (execution).
