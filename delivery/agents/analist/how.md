# How

## A — Epic intake (scope-confirmed sonrası)

1. Epic body: KEEP / DEFER / CUT tablosunu çıkar veya `scope_triage` oku.
2. Her KEEP satırı için child issue var mı? Yoksa → follow-up öner (# başlık).
3. Orphan child: scope’ta yok ama issue açık → orchestrator’a işaretle.
4. Her child body’de **AC bloğu** var mı? (`SKILL.md` şablonu)
5. Çıktı: epic comment `## Product analysis` → **status: ready | gaps**.

**ready:** orchestrator plan + path devam edebilir.  
**gaps:** follow-up listesi; mühür kuyruğu bekler.

## B — Leaf pre-seal (mühür öncesi, her #N)

1. `reference` özeti ile AC maddeleri 1:1 mi?
2. `tests_plan` her AC için en az bir doğrulama maddesi içeriyor mu?
3. **Out of scope** açık mı? (ponytail önleme)
4. Leaf çok büyükse → split önerisi (2+ issue).
5. Pure bugfix / AC zaten tam → kısa checklist, `status: ready`.

Fail → `## Scope gap` comment; orchestrator follow-up açar.

## C — Epic closure (§1 — analist lead)

`delivery/runbooks/epic-closure.md`:

1. KEEP ↔ child `leaf-done` eşleşmesi.
2. DEFER: label veya defer issue linki.
3. Zombie: `intake` / açık leaf.
4. Gap listesi → `epic_closure.gaps` (documenter formatlar).

Pass → orchestrator closure §2–3’e devreder.

## AC formatı (varsayılan)

Checkbox listesi. Gherkin yalnızca kritik akış (ödeme, kayıt, izin).

```markdown
## Acceptance criteria
- [ ] …

## Out of scope
- …

## Success signal (opsiyonel)
- …
```

## Contract
- **Input:** epic body, children, reference, tests_plan.
- **Output:** `## Product analysis` / `## Scope gap` comment, AC ↔ test mapping.
- **Done when:** `status: ready`; every AC mapped.
- **Forbidden:** code, seal, `epic-done`.
- **Handoff:** orchestrator (plan), tester (AC frozen).
