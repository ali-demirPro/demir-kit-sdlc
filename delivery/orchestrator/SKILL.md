---
name: delivery-orchestrator
description: Epic path routing, agent delegation, epic closure — never claim epic done without closure pass.
---

# orchestrator

Read in order:

1. `ROLE.md`, `how.md`, `communicates.md`, `dependencies.md`
2. `delivery/FLOW.md`
3. `delivery/policies/approval.md`
4. `delivery/policies/path-routing.md`
5. `delivery/runbooks/epic-closure.md`
6. `delivery/registry.yaml`

## Execute

- Select `path_id`; emit `delivery_path` on epic issue.
- Delegate only **active_agents**; document skips.
- Leaf complete → trigger human-qa template (`policies/human-qa-done.md`).
- All leaves `leaf-done` → run epic closure checklist; on pass → epic human-qa.
- No `src/` without `agent-approved` (legacy G1).
- Orca: `delivery/protocol/execution.md` after seal.

## Forbidden

- Saying epic is finished before `epic_closure.status: pass` and `epic-done` label.
