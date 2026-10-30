# AGENTS.md

## Repo

demir-kit 2.28 — delivery-first agent system. Docs, YAML and small bash/python
scripts; Python unittest suite and CI, no app build system or package manager.
"Correct" means the contract, registry, schemas and policies agree — `doctor.sh`
decides.

Version lives in `VERSION`; bump it with `CHANGELOG.md` and the README header.

## Commands

```bash
./delivery/scripts/doctor.sh              # full static check
./delivery/scripts/doctor.sh --strict     # warnings are errors (CI gate)
./delivery/scripts/doctor.sh --issue 12   # seal + evidence for one issue
./delivery/scripts/next-leaf.sh --claim   # dependency-aware queue
./delivery/scripts/guard.sh --issue 12    # source gate (G1) + risk escalation
./delivery/scripts/transition.sh --issue N --to leaf-done  # single-writer transition
./delivery/scripts/capabilities.py --matrix   # role x capability matrix
./delivery/scripts/variants.py --role designer # capability -> variant map
./delivery/scripts/profiles.py --project .        # profile composition
./delivery/scripts/standards.py --project . --check # project standards
./delivery/scripts/verify.py --project .          # read-only adaptation check
./delivery/scripts/adopt.py --project . --apply   # one-command SDLC injection
./delivery/scripts/brief.py 12              # leaf → agent brief
python3 -m unittest discover -s delivery/tests  # test suite
./delivery/scripts/resolver.py --surface web.app --platform web --stack next
./delivery/scripts/adapt.py --add platform.android  # capability diff; --apply writes .kit/capabilities.yaml
./delivery/scripts/eval.py --check           # eval scenarios (10+ per variant)
./delivery/scripts/detect.py --project . --json # project fingerprint
./delivery/scripts/learnings.py --all       # fleet öğrenim federasyonu
./delivery/scripts/init.py --project . --apply # project wiring
./delivery/scripts/vendor_sync.sh --target ../Product --check
./delivery/scripts/vendor_sync.sh --target ../Product --apply
./install.sh --with-platform              # Orca + v2 skills (local source)
```

Scripts are bash wrappers over `python3` (PyYAML required). There is no `make`.

## Layout

| Path | Role |
|------|------|
| `delivery/` | Active runtime: contract, protocol, policies, agents, schemas, scripts |
| v1 archive: `archive/v1.7/` | Legacy 1.x — never reference it as runtime; move paths when touching a file |
| `skills/` | v2 runtime skills, installed by `./install.sh` |
| `discovery/` | Staged next-phase agent (`growth/plan`); not installed or vendored |
| `ecosystem.yaml`, `kit.config.yaml` | Self-host wiring; this repo is its own product |

Runtime skills live in `skills/`; `./install.sh` installs them from the local tree.
`--legacy` restores the same set from the v1 archive (loud warning, no GitHub
fallback).

## Source of truth

- `delivery/CONTRACT.md` — states, T1–T9 transitions, risk model, DoD, invariants.
- `delivery/registry.yaml` — paths, agents, labels, risk globs.
- `delivery/schemas/` — `demir_kit_version: "2"` leaf/epic/evidence/closure.
- `delivery/policies/quality-gates.md` — mandatory gates per risk level.

If prose and registry disagree, registry + doctor win; fix the prose.

## Invariants

- Approval is issue + label. With `scope-confirmed` / `agent-approved`, do not ask.
- No source work before `agent-approved` (`guard.sh`).
- No `leaf-done` without evidence; no `epic-done` without closure `pass`.
- Implementer never approves; reviewers get isolated context.
- Risk C: `low`/`medium` auto-close, `high`/`critical` human, irreversible always human.
- One `executing` leaf per epic unless dependencies are disjoint.
- Contract change = VERSION + CHANGELOG + doctor green.

## Language

Docs are Turkish with English headings, labels and YAML keys. User-facing text:
short Turkish, max two sentences, no jargon (checkpoint, gate, YAML, worktree) —
see `delivery/policies/human-communication.md`.

## Observability

- Timeline = GitHub issue comments. Do **not** add timeline markdown files to the repo.
- Post a short Turkish update at seal, claim, CP/review result, leaf-done and epic
  closure: `python3 delivery/scripts/update.py --issue N --who … --what …`.
- Every update has an explicit `Onay:` line; request approval with
  `--approval yes --ask "…"` (adds `human-qa`).
- Epic closure: post the short `--kind summary` comment first (so decisions and
  problems are captured), then the detailed `report.py` comment; repeat the
  short summary in chat.
- Claim snapshots the main session cost (`.orchestration/usage-N.json`); the
  closure report shows the epic delta, not the whole-session total.
- End a work session with the same summary in chat.
- Never log chain-of-thought, prompts or secrets; only outcomes, decisions and problems.

## Verification

`./delivery/scripts/doctor.sh --strict` before finishing (0 warnings). CI strict is
wired by Epic 0 #4. For a sealed leaf also run `doctor.sh --issue N`; for source
changes run `guard.sh --issue N`.
