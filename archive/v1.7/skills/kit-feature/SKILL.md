---
name: kit-feature
description: >-
  Product owner command — scope KEEP/DEFER/CUT ONLY. Does NOT seal work packages,
  does NOT modify app source, does NOT run Orca gates. Alias for scope-triage phases F0–F4.
---

# kit-feature

**Canonical skill:** `${kit.root}/skills/scope-triage/SKILL.md`  
**Hard gates:** `${kit.root}/references/agent-phase-gates.md` (mandatory — read before acting)

Apply `human-communication.md` for all user messages.

## STOP — read first

You are in **kit-feature**, not kit-build. If the owner wants code or gates, say: *“Bunu kit-build #N ile mühürleyelim; şimdi sadece kapsam netleştiriyoruz.”*

| Forbidden | Allowed |
|-----------|---------|
| Edit `src/`, `app/`, `lib/` (app code) | Read/analyze code and UI |
| Label `agent-approved` | Label `scope-confirmed` on **parent/epic** only |
| `checkpoints`, `tests_plan`, `checkpoints_preapproved` in issue YAML | `scope_triage` (+ optional `feasibility`) on parent |
| `entry.kind: greenfield_product` for brownfield UI/epic | `feature` or epic parent without full factory seal |
| Orca run / worker / implement P0 bundle | `gh issue create` after F3 only |
| Seal parent with full work-package | Child issues: markdown + `intake` |

Before ending session: run `${kit.root}/tools/kit-agent-guard.sh` (or `scripts/kit-agent-guard.sh`) — must pass with **no app path diff**.

## Phases (do not skip or merge)

### F0 — Discover

- Read brief § Development bets, `docs/product/*`, session notes, repo (UI/components).
- Produce KEEP / DEFER / CUT table with effort bands.
- **Do not** create issues or change tracked files under app paths.

### F1 — Confirm scope

- Present table in Turkish; ask owner to confirm or adjust (P0 vs defer P1/P2).
- **Do not** interpret “devam” as implementation.

### F2 — Issue plan (chat only)

- Propose parent title + child breakdown + labels (`intake` on children).
- Ask: *“Bu planla GitHub issue’larını açayım mı?”*
- **Wait** for explicit yes (“issue aç”, “basla” **after** F1 scope OK).

### F3 — Open issues (only after F2 yes)

- Parent: human summary + **minimal** ` ```yaml demir-kit` block — **`scope_triage` only** (see `agent-phase-gates.md` allowed keys).
- Children: markdown acceptance bullets; `intake`; “Üst iş: #parent”.
- **No** full work-package on parent. **No** code.

### F4 — Close triage

- Label parent **`scope-confirmed`**.
- Sync **defer** items to `docs/architecture/evolution-roadmap.md` if needed.
- Tell owner next step: **kit-build** on **one leaf issue at a time** (#3, #4, …).

## Trigger disambiguation

| Owner says | Action |
|------------|--------|
| “basla” / “issue aç” (scope already OK) | F3 only |
| “uygula”, “kod yaz”, “bitir”, “P0 yap” | **Refuse in kit-feature** → offer **kit-build #N** |
| “kit-build” | Hand off to **kit-build** skill |

## Do not

- Re-run full kit-envision council if brief is approved.
- Implement or batch-implement epic children.
- Anti-pattern: `examples/anti-patterns/kit-feature-premature-seal.md`

## Complete

`scope-confirmed` on epic; children `intake`; **zero** app source diff; guard script OK.
