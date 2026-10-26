# Coordinator blocker playbook

VB **Adaptive Loop** blocker kurallarının demir-kit sürümü. Orca coordinator + `human-communication.md`.

## Labels

| Label | Meaning |
|-------|---------|
| `blocked` | External or cross-CP dependency |
| `architect-revise` | Architect output-review open |
| `scope-confirmed` | Triage locked |
| `discovery-approved` | Envision / direction locked (`discovery-done` deprecated) |

## Detection rules

Evaluate after each CP or on weekly adaptive check-in.

### Dependency block

```
IF checkpoint B.depends_on includes A AND A not evidence-complete:
  SET label blocked on issue B
  SUGGEST (human): "X bitmeden Y'ye geçemeyiz. Şimdilik Z (bağımsız CP) yapılabilir."
  LIST alternative CPs with disjoint depends_on
```

### API / backend wait (example)

```
IF surface ios.* blocked on backend contract AND backend CP < 100%:
  SUGGEST: mock API or UI-only CP per ui_scope; ADR note for migration
```

### Architecture baseline

```
IF factory.architecture_baseline_required
   AND architecture_baseline NOT IN factory.waived_baselines
   AND NOT label architecture-baseline-done:
  BLOCK agent-approved feature runs
  SUGGEST: complete baseline epic first OR document waive in decisions + brief Handoff
```

### Commercial baseline

```
IF factory.commercial_baseline_required
   AND commercial_baseline NOT IN factory.waived_baselines
   AND NOT label commercial-baseline-done:
  BLOCK greenfield implementation runs touching marketing.site or monetization
  SUGGEST: complete commercial_baseline epic OR waived_baselines + brief artifacts
```

### Architect revise

```
IF verdict revise_required AND round >= 3:
  ask human: waive minor findings or pause scope
```

### Velocity (adaptive)

```
IF planned_cp_hours * velocity_ratio > available_hours_for_week
  AND velocity_ratio < 0.7 for 2 consecutive weekly check-ins:
  SUGGEST scope-triage re-open: defer lowest ROI keep items to phase-2
  INVOLVE solution-architect refactor-proposal optional
```

### Free tier (tier-review)

```
IF cost-and-tiers.md zone red for service S:
  BLOCK new CP that enables paid feature on S without ADR
  SUGGEST tier-review mode + exit plan issues
```

## Mitigation output format

Post GitHub comment (technical OK on issue):

```markdown
## Blocker — {{short title}}

**Affected:** CP-… / surface …
**Cause:** …
**Suggestion:** …
**Alternatives:** …
```

User-facing `ask` text: 2 sentences + options.

## Unblock

- Dependency resolved → remove `blocked`, re-run `health-check`
- User override → `decisions` entry + optional amend

## See also

- `orchestration/weekly-adaptive-loop.md`
- `references/architecture-stewardship.md`
