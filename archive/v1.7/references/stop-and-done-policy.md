# Durak ve tamamlama politikası

Kalite kapıları **geçilmeden** iş tamamlanmış sayılmaz; agent veya otomasyon bunu atlayamaz.

## Orca supervised workers

- Worker sends `worker_done` **only** after behavior exit 0, UI protocol pass (if applicable), dual adversarial approval.
- Coordinator **rejects** premature `worker_done` if evidence comment template incomplete.
- Use `orchestration send --outcome failed` when stuck; `ask` user in human language.

## Cursor / single-pane agents (no Orca dispatch)

- Do not mark issue `done` or CP complete without running gate commands.
- Prefer Orca `worker-start` for demir-kit execution; if impossible, document gate outputs in issue comment before closing.

## Optional agent stop hook (user-installed)

On agent stop: script checks open issue label `executing` and last evidence comment for current CP — if missing, return exit code 2 with message "demir-kit gates incomplete". See Cursor create-hook skill; not bundled in demir-kit.

## Automation

Automations must not remove `agent-approved` or set `done` without human QA gate resolve.
