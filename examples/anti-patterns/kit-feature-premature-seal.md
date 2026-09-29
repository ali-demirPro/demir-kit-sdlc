# Anti-pattern: kit-feature → work-package + implementation

**Symptom:** Owner invoked **kit-feature**; agent ran scope analysis (good), then:

1. Created parent issue with **full** `demir-kit` YAML (`checkpoints`, `tests_plan`, `greenfield_product`, `mode: bootstrap`).
2. Labeled parent `scope-confirmed` **and** treated it as executable.
3. Created child issues with `intake` (good) but **implemented all P0 in `src/`** without **kit-build**, **`agent-approved`**, **health-check**, or **Orca gates**.

**Why wrong:** `kit-feature` ends at **F4** (`scope-confirmed`, minimal YAML). Mühür = **kit-build** on **each leaf** issue. Gates = Orca CPs after seal.

**Correct flow:**

1. kit-feature F0–F1: analysis + KEEP/DEFER table → owner confirms P0 only.
2. F2: plan parent + 6 children in chat.
3. F3: owner “issue aç” → create issues; parent YAML = **`scope_triage` only**.
4. Stop — **no `src/` diff**.
5. kit-build **#3** (first child): factory-routing, init if needed, full YAML, `agent-approved`, health-check, Orca.
6. Implement only scope of **#3**; repeat for #4…#8.

**Skill fix:** `references/agent-phase-gates.md`, `skills/kit-feature/SKILL.md`.
