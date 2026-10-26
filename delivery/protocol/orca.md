# Orca supervised workers

Orca is the execution engine for supervised workers. The delivery contract stays
in GitHub; Orca only runs and settles work.

## Readiness

```bash
./delivery/scripts/orca_smoke.sh
```

Checks `orca status --json` and the version-matched orchestration skill. It does
**not** start a worker. `--create-run` creates a Run only.

## Task specs

```bash
python3 delivery/scripts/orca_plan.py <issue>          # human output
python3 delivery/scripts/orca_plan.py <issue> --json   # machine output
python3 delivery/scripts/orca_plan.py <issue> --write /tmp/orca-plan
```

One sealed leaf → one task per checkpoint. Role mapping: `gates.ui` → designer,
otherwise developer. Every spec names target, change, constraints, ownership and
observable acceptance (`doctor.sh --issue N --checkpoint CP-x`).

## Supervised loop

```bash
orca orchestration run-create --objective "demir-kit #N" --json
orca orchestration worker-start --spec "<spec>" --worktree current --agent opencode2 --json
orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 900000 --json
orca orchestration worker-release --dispatch <dispatch_id> --json
```

On this host the working launcher is `opencode2`; `opencode` may be disabled.
`--name`, `--setup` and `--repo` are new-worktree options — with
`--worktree current` Orca rejects them.

Rules:

- `worker-start --spec` creates the Task and attempt; capture `taskId` and
  `dispatchId` from the receipt. `--setup`/`--name` are only for new worktrees;
  Orca rejects them with `--worktree current`.
- Workers send `worker_done` themselves (injected preamble); never encode success
  only in prose.
- A timeout is a checkpoint, not a failure. Inspect `worker-list` before acting.
- Release only after an accepted settlement.
- Read-only smoke first; coding workers only on sealed leaves.

## Evidence

Record the Orca identity in the evidence block:

```yaml
worker:
  run_id: run_…
  task_id: task_…
  dispatch_id: ctx_…
  agent: opencode2
  outcome: succeeded
```

## Degrade mode

No Orca → single-pane protocol in [execution.md](execution.md). The same gates,
evidence and labels apply; only the worker transport changes.

## Safety

- No production deploy, store submit, pricing or destructive migration without
  a human gate.
- A worker must not approve its own work; reviewers stay isolated.
- If a worker edits outside its CP, stop it and open a follow-up issue.
