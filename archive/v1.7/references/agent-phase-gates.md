# Agent phase gates (hard blocks)

Sürüm: demir-kit **1.7.3**. **Zorunlu** — owner skill’ler ve `work-package` bu kurallara uyar. İhlal = protokol hatası.

Canonical journey: `product-lifecycle.md`. İnsan dili: `human-communication.md`.

## Owner commands → allowed phases

| Owner says | Skill | May end at | Next command |
|------------|-------|------------|--------------|
| kit-setup | kit-setup | wiring + envision done | kit-feature / kit-build |
| kit-feature | scope-triage | `scope-confirmed` + roadmap | **kit-build** |
| kit-build | work-package | `agent-approved` + health-check | Orca |
| kit-build-change | work-package-amend | bumped `package_version` | Orca resume |
| kit-upgrade | kit-upgrade | vendor VERSION sync | — |

## Global hard blocks (all skills unless noted)

| # | Block | Rationale |
|---|--------|-----------|
| G1 | **No `src/` app code** (paths in `kit.config.yaml` `factory.app_paths` or default `src/`, `app/`, `lib/`) without label **`agent-approved`** on the **tracked issue** for this work | Implementation = sealed package only |
| G2 | **No label `agent-approved`** except during **kit-build** / **work-package** seal on a **leaf** issue | Triage ≠ executable |
| G3 | **No Orca** `run-create`, `worker-start`, bulk CP implementation without **G2** + **health-check** `ready: true` | Gates live in Orca phase |
| G4 | **No `gh issue create`** until owner explicitly agreed issue plan (F2→F3); “basla” alone = issues only if F1 scope table already confirmed | Conversation before tracker |
| G5 | Issue body **`checkpoints`**, **`tests_plan`**, **`checkpoints_preapproved`** only on issues that **kit-build** is sealing now | No premature mühür |
| G6 | Brownfield product repo: default **`entry.kind: feature`** — not `greenfield_product` / `mode: bootstrap` for UI/epic work | Wrong factory entry |
| G7 | **Parent/epic issues:** `scope_triage` + human summary only — **no** full work-package YAML on parent | Children sealed individually |
| G8 | Run **`tools/kit-agent-guard.sh`** before claiming “implementation done” (or before commit if agent commits) | Mechanical check |

## kit-feature / scope-triage — phases (do not skip)

| Phase | Name | Agent may | Agent must NOT |
|-------|------|-----------|----------------|
| **F0** | Discover | Read repo, UI/code analysis, draft KEEP/DEFER/CUT table | `gh issue create`, edit `src/`, `agent-approved`, work-package YAML |
| **F1** | Confirm scope | Ask owner to confirm/adjust table (Turkish, options) | Issue create, code |
| **F2** | Issue plan | Propose parent/child titles + labels (`intake`, `scope-confirmed` on parent only) in **chat** | `gh issue create` until F3 |
| **F3** | Open issues | Create issues **only if** owner said e.g. “issue aç”, “GitHub’a yaz”, “basla” **after F1** | Full `demir-kit` block with checkpoints; seal |
| **F4** | Close | Update parent with **minimal** YAML (`scope_triage`, optional `feasibility`); label `scope-confirmed`; sync defer → `evolution-roadmap.md` | `src/`, `agent-approved`, Orca |

**F3 parent issue YAML — allowed keys only:** `demir_kit_version`, `scope_triage`, `feasibility`, `envision` (pointer), `decisions` (triage notes).  
**Forbidden on parent:** `checkpoints`, `tests_plan`, `checkpoints_preapproved`, `reference` (full), `factory` (full profile), `mode: bootstrap`.

**F3 child issues:** Markdown only + `intake` label; link “Üst iş: #N”. **No** ` ```yaml demir-kit` ** until kit-build on that child.

**Trigger disambiguation (skill text for agents):**

| Owner phrase | Means |
|--------------|--------|
| “basla”, “devam”, “issue aç” (after scope OK) | F3 issue create — **not** code |
| “uygula”, “kod yaz”, “implement”, “kit-build #N” | Leave kit-feature — run **kit-build** |

## kit-build / work-package — phases

| Phase | Gate |
|-------|------|
| B0 | Target issue **#N** is a **leaf** (or explicit single feature issue), not scope-only parent |
| B1 | Issue has **`scope-confirmed`** on epic/parent or `scope_triage.confirmed` on this issue |
| B2 | Run **factory-routing** if `factory.profile` / `entry.kind` unset |
| B3 | **kit-init** if `ecosystem.yaml` missing (autonomous) |
| B4 | **test-plan** fills `tests_plan`; **checkpoint-planner** if needed |
| B5 | Seal: full YAML + **`agent-approved`** |
| B6 | **health-check** → Orca only if `ready: true` |
| B7 | Implementation in **`src/`** only for **#N** (worktree recommended); not whole epic in one session |

**Block:** Sealing parent #2 with 5 CPs while children are `intake` — **invalid**. Seal **#3** … **#8** one at a time.

## kit-build-change

- Only issues already **`agent-approved`** with sealed YAML.
- No new `src/` scope beyond amend audit; same G1.

## kit-upgrade

- Only `${kit.root}`, `kit.config.yaml` `kit.version`; **never** `src/`, `docs/product/` content changes.

## kit-envision / kit-setup

- No `ecosystem.yaml` commit before `discovery-approved`.
- No `agent-approved` on envision tracking issue.

## Internal gate skills (Orca workers)

- Invoked by coordinator **after** B6 — not by owner chat during kit-feature.

## Verification

```bash
# From product repo root — fail if src/ changed without approved issue
./scripts/kit-agent-guard.sh
./scripts/kit-agent-guard.sh --issue 3   # optional: verify label on GitHub
```

## Anti-pattern reference

`examples/anti-patterns/kit-feature-premature-seal.md`
