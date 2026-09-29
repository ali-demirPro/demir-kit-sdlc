# Weekly adaptive loop

VB Layer 4 — **GitHub + Orca**; `03_WEEKLY/` klasörü yok.

## Cadence (suggested automation cron)

| Day | Purpose | Skill |
|-----|---------|--------|
| Monday | Pre-flight: week goals, blockers, effort re-estimate | coordinator + `coordinator-blockers.md` |
| Wednesday | Mid-week: % CP vs plan, early warning | coordinator |
| Friday | Retro: learnings, next week forecast | `learnings` + optional `solution-architect` `tier-review` if monthly cadence aligns |

Trigger manually via user intent (`user-intents.md`) or Orca automation on epic label `executing`.

## Monday comment template

```markdown
## Haftalık pre-flight — {{week}}

**Hedef CP'ler:** …
**Blocker taraması:** … (see coordinator-blockers)
**Tahmini efor:** … h (velocity ayarı: …%)

**Öneri:** …

Onay: bu hafta planı uygun mu?
```

## Wednesday template

```markdown
## Mid-week — {{week}}

**Tamamlanan:** … / … CP
**Beklenen vs gerçek:** …%
**Erken uyarı:** …

**Öneri:** … (defer / parallel CP / mock API)
```

## Friday template

```markdown
## Haftalık retro — {{week}}

**Shipped:** …
**Öğrenilenler:** … (link `learning` issues)
**Gelecek hafta:** … CP, … h

**Scope:** scope-triage yeniden açılsın mı? …
```

Post with `gh issue comment` on epic; append bullets to `docs/agent/learnings.md` only if recurring.

## Issue YAML (optional on epic)

```yaml
adaptive:
  cadence: weekly
  velocity_warning_threshold: 0.7
  consecutive_slow_weeks: 0
  last_check_in: "2026-09-29"
```

When `consecutive_slow_weeks >= 2` → run `scope-triage` suggestion per blocker playbook.

## Progress visibility

Prefer GitHub Project fields or issue checklist on CP list; ASCII Gantt in chat optional, not required (MVO).
