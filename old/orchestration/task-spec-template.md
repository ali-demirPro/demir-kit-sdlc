# Orca task spec template (per checkpoint)

Replace: `{{ISSUE}}`, `{{CP_ID}}`, `{{CP_TITLE}}`, `{{UI_SCOPE}}`, `{{GATE_CMD}}`, `{{REFERENCE_SUMMARY}}`.

---

## Behavior task

```
demir-kit {{CP_ID}}: {{CP_TITLE}} — behavior
Issue #{{ISSUE}} | tests_plan cases for {{CP_ID}} only
Reference: {{REFERENCE_SUMMARY}}

Skill: behavior-gate. Run gate: {{GATE_CMD}}
Do not worker_done until exit 0.
```

## UI tasks (dispatch TWO workers)

```
demir-kit {{CP_ID}} — ui-gate MODE=visual
ui_scope: {{UI_SCOPE}}
Reference/prototype only — no repo coding conventions.
Output JSON per ui-gate skill (comparison_valid, findings).
```

```
demir-kit {{CP_ID}} — ui-gate MODE=interaction
(same isolation rules)
```

## Adversarial tasks (dispatch TWO, then fixer)

```
demir-kit {{CP_ID}} — adversarial reviewer-a
```

```
demir-kit {{CP_ID}} — adversarial reviewer-b
(fresh context; do not read reviewer-a output)
```

Fixer task only after merged findings. Re-run both reviewers until both approved.

## After CP

Coordinator posts evidence comment template. Then next CP or human-qa phase.
