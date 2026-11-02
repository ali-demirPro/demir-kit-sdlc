---
name: adversarial-review
description: >-
  Independent reviewers (1 for low/medium, 2 for high/critical), a fixer, and
  re-review; every required reviewer must approve. Use when a checkpoint has
  open findings, after any fix, or when doctor asks for reviewer approvals.
---

# adversarial-review

Matrix: `delivery/policies/quality-gates.md`.

## Roles (separate workers)

1. **reviewer-a** — assume the code is wrong; numbered findings against
   `docs/architecture/`, ADRs, UI guidelines and lint. Do not repeat open
   architect findings unless still present in the diff.
2. **reviewer-b** — same inputs, fresh context; must not see reviewer-a output
   until both submit. The coordinator merges findings.
3. **fixer** — only the listed items.

Reviewer count: 1 for `low`/`medium`, 2 for `high`/`critical`.

## Review packet and delta

Start from the packet instead of the whole repo:

```bash
python3 delivery/scripts/review_packet.py --issue <N> --cp CP-1 --commit <sha>
```

- Packet: CP brief, AC/test rows, open findings, diff (max 12 KB).
- After a fix: `--delta <base>`; re-check only changed hunks and open findings.
- Script: [review_packet.py](../../delivery/scripts/review_packet.py).

## Loop

- Open finding → fixer → re-run the required reviewers.
- Max 5 rounds, then `blocked` + one human-language question.

## Approval

Each reviewer returns `{ "approved": true, "findings": [] }`.

## Regression

1. Re-run the behavior gate for this CP.
2. UI files changed → re-run `ui-gate` visual + interaction.

## Evidence

Record `reviews.adversarial` in `delivery/protocol/evidence.md`; `worker_done`
only after approval.

## Done when

Her zorunlu reviewer `approved` döndürdü, açık bulgu kalmadı ve
`reviews.adversarial` evidence'a yazıldı.
