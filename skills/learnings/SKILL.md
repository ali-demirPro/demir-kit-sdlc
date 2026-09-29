---
name: learnings
description: >-
  Capture human QA feedback for future agents. Prefer tracker learning issues;
  optional short bullets in docs/agent/learnings.md with issue links only.
---

# learnings

## After human QA

1. Summarize feedback in tracker comment on the work issue.
2. If recurring: create or update issue labeled `learning` OR append to `docs/agent/learnings.md` as one line + URL.
3. Do **not** duplicate full work package into repo.

## Before workers start

Read `docs/agent/learnings.md` and GitHub issues labeled `learning` if the project uses them.

## Weekly retrospective (adaptive loop)

On Friday check-in (`orchestration/weekly-adaptive-loop.md`):

1. Bullet what shipped vs planned (CP ids).
2. Note estimate drift (+/− hours) for coordinator velocity.
3. If pattern repeats → `learning` issue or one line in `docs/agent/learnings.md`.

Trigger `scope-triage` suggestion when `adaptive.consecutive_slow_weeks >= 2` (`coordinator-blockers.md`).

## Orca

Optional `gh issue comment` on the work issue; coordinator may `worktree set --comment` for progress.
