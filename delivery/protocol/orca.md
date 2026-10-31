# Orca supervised workers

Orca is the execution engine for supervised workers. The delivery contract stays
in GitHub; Orca only runs and settles work.

## Readiness

```bash
./delivery/scripts/orca_smoke.sh
python3 delivery/scripts/orca_capabilities.py --check orchestration.worker-start:task,model,effort
```

Checks `orca status --json` and the version-matched orchestration skill. It does
**not** start a worker. `--create-run` creates a Run only. Product projects do
not compare Orca versions; `agent-context` feature detection is the contract.

## Task specs

```bash
python3 delivery/scripts/orca_plan.py <issue>          # human output
python3 delivery/scripts/orca_plan.py <issue> --json   # machine output
python3 delivery/scripts/orca_plan.py <issue> --write /tmp/orca-plan
```

One sealed leaf → one task per checkpoint. Role mapping: `gates.ui` → designer,
otherwise developer. Every spec names target, change, constraints, ownership and
observable acceptance (`doctor.sh --issue N --checkpoint CP-x`).

## Epic worktree

One epic owns one worktree and one branch. Leaves reuse it; never create a
worktree per leaf.

```bash
python3 delivery/scripts/epic_worktree.py ensure --epic <E> --json
python3 delivery/scripts/epic_worktree.py check  --epic <E> --json
python3 delivery/scripts/epic_worktree.py sync   --epic <E>
python3 delivery/scripts/epic_worktree.py remove --epic <E>
python3 delivery/scripts/epic_worktree.py prune
```

- `ensure` is idempotent: reuses `epic-<E>`; creates it once with
  `orca worktree create --name epic-<E> --issue <E>`.
- `check` rejects the main checkout, a different worktree and a missing run.
- `sync` merges `origin/main`; rebase is forbidden because it rewrites evidence
  commit SHAs.
- `remove` runs after the epic PR merge; `--keep-worktree` on `epic-done` keeps it.
- `prune` lists (and with `--apply` removes) worktrees whose epic is closed.
- `compat.py` is the kit-maintenance check: it names the 66 Orca commands/flags
  the kit relies on. Products do not run it in CI.
- `worktree set` mirrors state: `--comment`, `--workspace-status`,
  `--unread/--read`, `--issue/--pr`, `--reference`. `update.py` and
  `transition.py` call it automatically.
- `orca worktree ps --json` is the fleet view; `orca ports` gives the dev-server
  URL for UI gates.

## Task, message and gate flow

```bash
orca orchestration task-create --spec "<CP spec>" --task-title "<CP>" \
  --deps '["task_<önceki>"]' --run <run_id> --json
orca orchestration worker-start --task <task_id> --worktree <epic path> \
  --agent opencode2 --run <run_id> [--model <id> --effort <level>] --json
orca orchestration task-update --id <task_id> --status completed --run <run_id> --json
orca orchestration ask --question "..." --options "a,b" --json
orca orchestration reply --id <msg_id> --body "..." --json
orca orchestration gate-create --task <task_id> --question "..." --options '["approve","revise"]' --json
orca orchestration gate-resolve --id <gate_id> --resolution approve --json
orca orchestration inbox --json
```

- One Run per epic; resume with `run-use`, never a second `run-create`.
- One Task per CP with `--deps`; `worker-start --task` keeps provenance.
- Per-role launch defaults live in `kit.config.yaml`:
  `orca.role_defaults.developer: {agent: opencode2, model: …, effort: high}`.
- Human decisions are Orca gates + GitHub `human-qa`; resolve both.
- Worker questions use `ask/reply`, not local TUI prompts.

## Supervised loop

```bash
orca orchestration run-create --objective "epic #E" --json
orca orchestration task-create --spec "<spec>" --json
orca orchestration worker-start --spec "<spec>" --worktree <epic-E path> --agent opencode2 --json
orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 900000 --json
orca orchestration worker-release --dispatch <dispatch_id> --json
```

On this host the working launcher is `opencode2`; `opencode` may be disabled.
`--name`, `--setup` and `--repo` are new-worktree options — with
`--worktree <path>` Orca rejects them.

Rules:

- `worker-start --spec` creates the Task and attempt; capture `taskId` and
  `dispatchId` from the receipt. `--setup`/`--name` are only for new worktrees.
- Workers send `worker_done` themselves (injected preamble); never encode success
  only in prose.
- A timeout is a checkpoint, not a failure. Inspect `worker-list` before acting.
- Release only after an accepted settlement.
- Read-only smoke first; coding workers only on sealed leaves.
- Native subagents are not a substitute for `worker-start` when Orca is running.

## Parallel waves

Start every independent task before waiting; do not serialize tasks that have no
dependency.

```bash
python3 delivery/scripts/orca_wave.py --issue <N> --execute --json
```

- `--dry-run` (default) prints the exact `run-create` + `worker-start` commands.
- `--from-json` accepts a plan-like `{tasks: [{id, spec, deps}]}` for smoke or
  custom waves.
- `check --wait` may return a batch with one **or several** `worker_done`
  messages. Process the whole batch, acknowledge it once, then wait again.
- Release each settled dispatch; leave a missing worker for inspection.
- Dependencies belong to a later wave, not to a pending task in this one.
- `--dag` uses each task's `deps` to run dependency waves: start the ready wave,
  wait for it, then start the next. Unknown deps and cycles fail fast.
- A failed `worker_done` stops the DAG; dependent tasks do not start.
- `--notify --issue N` posts one short human summary (no task/dispatch IDs) after
  the wave; if anything is missing it requests approval.

## Scheduled automations

Templates live in `delivery/automations/` and are disabled by default:

```bash
python3 delivery/scripts/automations.py templates
python3 delivery/scripts/automations.py create --template stale-lease          # plan only
python3 delivery/scripts/automations.py create --template stale-lease --apply  # disabled
python3 delivery/scripts/automations.py list
```

Stale lease, weekly doctor, PR queue and weekly report are examples, not
mandatory jobs. `--enable` is an explicit human action.

## Evidence

Record the Orca identity in the evidence block:

```yaml
worker:
  run_id: run_…
  task_id: task_…
  dispatch_id: ctx_…
  agent: opencode2
  outcome: succeeded
worktree:
  name: epic-15
  path: /Users/you/orca/workspaces/Product/epic-15
  branch: epic-15
  epic: 15
```

For a parallel wave use a `workers:` list with one entry per dispatch.

```yaml
workers:
  - { run_id: run_…, task_id: task_…, dispatch_id: ctx_…, agent: opencode2, outcome: succeeded }
  - { run_id: run_…, task_id: task_…, dispatch_id: ctx_…, agent: opencode2, outcome: succeeded }
```

## Degrade mode

No Orca → single-pane protocol in [execution.md](execution.md). The same gates,
evidence and labels apply; only the worker transport changes.

## Safety

- No production deploy, store submit, pricing or destructive migration without
  a human gate.
- A worker must not approve its own work; reviewers stay isolated.
- If a worker edits outside its CP, stop it and open a follow-up issue.
