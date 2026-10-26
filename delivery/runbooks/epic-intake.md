# Epic intake

Sözleşme: [CONTRACT.md](../CONTRACT.md) · Akış: [FLOW.md](../FLOW.md)

1. `gh issue view <epic>` — `scope-confirmed` ve child listesi.
2. Orchestrator: epic + children + `ecosystem.yaml`.
3. **Path:** `registry.yaml` `paths` + `signals` → `path_id`
   ([path-routing](../policies/path-routing.md)).
4. **Onay:** label yeterli; HITL sorma ([approval](../policies/approval.md)).
5. Architect: CP sırası + `depends_on`; boundary riski varsa gate işaretle.
6. Analist: AC netliği; gap varsa follow-up issue.
7. Her **leaf:** [seal](../protocol/seal.md) → `agent-approved` → [health-check](../protocol/health-check.md)
   → `next-leaf --claim` → `executing`.
8. CP döngüsü: behavior → review → [evidence](../protocol/evidence.md)
   ([execution](../protocol/execution.md)).
9. Leaf kapanışı: `doctor.sh --issue N --checkpoint CP-x`; risk `low`/`medium`
   otomatik `leaf-done`, `high`/`critical` insan QA.
10. Tüm leaf'ler `leaf-done`/`deferred` → [epic-closure](epic-closure.md) →
    `pass` → epic insan kabulü → `epic-done`.

## Kurallar

- `agent-approved` olmadan kaynak değişmez ([guard](../../delivery/scripts/guard.sh)).
- Evidence'sız `leaf-done`, closure'sız `epic-done` yok.
- "Epic bitti" denmez; yalnızca closure `pass`/`fail`.
