# Orca entegrasyonu (demir-kit)

Sürüm: demir-kit **1.7.1**. Journey: `product-lifecycle.md`.

demir-kit **Orca’yı yeniden implemente etmez**. Coordinator her zaman:

1. `ORCA skills get orchestration --full` (Experimental açık, `orca status --json` OK)
2. `ORCA skills get orca-cli` (worktree, terminal, browser, emulator)
3. Bu dosya + `feature-flow-dag.md` + `gate-contract.md`

`ORCA` = oturum için çözülen `orca` / `orca-dev` / `ORCA_CLI_COMMAND` binary’si.

## demir-kit vs Orca sorumluluk

| İş | Orca | demir-kit |
|----|------|-----------|
| Envision / discovery packaging | `terminal send` veya chat run | `kit-envision` + `orchestration/packaging-run-prompt.md` |
| İş paketi mühürü, GitHub issue body | — | `work-package` skill + `gh` |
| Run / Task DAG / worker takibi | `run-create`, `task-create`, `worker-start`, `check` | Checkpoint → task spec şablonu |
| Worker bitti | `send --type worker_done` | Gate geçince coordinator gönderir |
| İnsan sorusu | `orchestration ask` | `human-communication.md` |
| İnsan onayı (plan sonrası QA) | `gate-create` / `gate-resolve` | Tracker label `human-qa` → `done` |
| Issue-linked worktree | `worktree create --issue N` | `tracker-policy.md` |
| Behavior doğrulama | `terminal create --command "…"` | `ecosystem.yaml` gate komutu |
| Web UI gate | `goto`, `snapshot`, `screenshot`, `set device` | `ui-gate` skill |
| Flutter / mobil UI | `orca-emulator`, `orca-emulator-android` skills | `ui-gate` + surface config |
| Tek seferlik prompt (izleme yok) | `terminal send` | **Kullanma** (supervised CP için) |
| Kuyruk / zamanlama | `automations` + `--precheck` | `templates/orchestration/automation-prompt.md` |
| Plan görselleştirme | `artifacts share` (HTML) | İsteğe bağlı; viewer opsiyonel |

## Run types

| Objective | Prompt / skill |
|-----------|----------------|
| `kit-envision <repo>` | `orchestration/packaging-run-prompt.md` |
| `demir-kit issue #N` | `templates/orchestration/automation-prompt.md` |

## GitHub (tek tracker)

```bash
gh issue view <N> --json title,body,labels,url
gh issue create --title "..." --body-file /tmp/body.md --label agent-approved
gh issue edit <N> --add-label executing --remove-label packaging
gh issue comment <N> --body "CP-2: behavior gate passed"
```

Worktree:

```bash
orca worktree create --name wp-<N> --issue <N> --agent claude --setup run --json
orca worktree set --worktree active --comment "CP-1 tamamlandı" --json
```

## Coordinator döngüsü (özet)

```bash
orca orchestration run-create --objective "demir-kit issue #<N>" --json
orca orchestration worker-start --task <taskId> --worktree new-child --name cp-1 --agent codex --setup run --json
orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 900000 --json
```

## Skill paketleri (Orca resmi)

```bash
npx skills add https://github.com/stablyai/orca --skill orchestration --global
npx skills add https://github.com/stablyai/orca --skill orca-cli --global
```

Mobil: `orca-emulator`, `orca-emulator-android`.

## Orca ADE (ürün repo)

1. `git clone` → `vendor/demir-kit`
2. **`kit-setup`** — `kit.config.yaml`, `kit.root`
3. **`kit-envision`** — `discovery-approved`
4. **`kit-init`** — `envision-handoff.md`
5. Fabrika → **`agent-approved`** → automation prompt

Coordinator task spec skill path: `{kit.root}/skills/<name>/SKILL.md`. Entry: `skills/kit/SKILL.md`.

## Plugin (sonra)

[orca-workflow-skills](https://github.com/stablyai/orca-workflow-skills) — `orca-plugin.json` phase 2.
