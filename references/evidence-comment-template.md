# GitHub evidence comment (per checkpoint)

Coordinator posts after all gates for a CP pass. Copy, fill, `gh issue comment`.

```markdown
## demir-kit evidence — {{CP_ID}}: {{CP_TITLE}}

**Commit:** {{SHA or "pending PR"}}
**Behavior gate:** `{{command}}` → exit 0
**Architect:** {{approved|revise_required|skipped}} — findings: {{AR count or "none"}}
**Commercial:** {{approved|revise_required|skipped}} — findings: {{CR count or "none"}}
**UI gate:** {{pass|skipped}} — scope: {{ui_scope or "n/a"}}
**Adversarial:** reviewer-a {{approved}}, reviewer-b {{approved}}

### Tests (from tests_plan)
- [x] {{case name}} — {{one line result}}

### UI review
- Comparison: {{valid|invalid}} (invalid → re-capture same state)
- Findings fixed: {{count}}

### Notes
{{optional Turkish summary for humans}}
```

Archive screenshots via Orca `artifacts share` and link URL here when useful.
