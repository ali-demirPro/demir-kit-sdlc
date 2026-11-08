---
name: behavior-gate
description: >-
  Red-green TDD for one checkpoint: failing test first, ecosystem gate command
  via Orca, exit 0 before worker_done. Use when a checkpoint starts, when the
  gate fails, or when doctor asks for behavior evidence.
---

# behavior-gate

Contract: `delivery/policies/quality-gates.md` (behavior).
Communication: `delivery/policies/human-communication.md`.

## Steps

1. Read the CP acceptance criteria and `tests_plan` cases from the issue seal.
2. Write tests (or doc checks); run the `ecosystem.yaml` gate command with
   `{checkpoint}` replaced — expect fail first.
3. Implement the minimal scope.
4. Re-run the gate — exit `0`.
5. Post evidence (`delivery/protocol/evidence.md`), then `worker_done`.

## Gate command

```bash
./delivery/scripts/gate.sh --issue <N> --checkpoint CP-1
```

With `--issue` the gate checks seal/evidence plus the suites the changes
require; without it (`ecosystem.yaml` form, `{checkpoint}` replaced) only the
checkpoint id format and those suites are checked.

## Orca

Prefer `orca terminal create --command "<gate>"` + `terminal wait` over ad-hoc
shell outside the worktree.

## Salt-okur kapı

Kapı depoyu değiştirmez; düzeltici adım (yerelleştirme birleştirme, kod üretimi)
`--fix` ile ayrı koşar. Düzeltici komutlar `ecosystem.yaml` yüzeyinde `gates.fix`
alanında tanımlanır; `--fix` yoksa koşmaz. Kontrol kapısı salt-okurdur: düzeltme
koşmadıysa `git status --short` boş kalmalı; izlenmeyen yeni dosya da kirli sayılır.

## Blockers

Gate limit (3 rounds) or environment failure → `blocked` + one human-language
question. Do not silently pass a failing gate.

## Done when

Gate komutu `{checkpoint}` ile `exit 0` verdi, test önce kırmızıydı ve evidence
`tests` bloğu yazıldı.
