# Tracker politikası (GitHub)

## Tek kaynak

- İş paketi, scope, checkpoint listesi, durum: **yalnızca GitHub Issues**.
- Repoda `work-packages/`, `WP-*.md` **yok**.

## Label’lar

`templates/github/labels.json` ile uyumlu:

| Label | Anlam |
|-------|--------|
| `intake` | Taslak |
| `packaging` | `work-package` skill aktif |
| `agent-approved` | Mühürlendi; Orca yürütebilir |
| `executing` | Checkpoint döngüsü |
| `human-qa` | Makine gate’leri bitti; ürün denemesi |
| `done` | Kapandı |
| `blocked` | Dış bağımlılık |
| `learning` | Meta öğrenme (opsiyonel) |

## Epic

- Parent issue + child issues veya task list.
- Parent `done` ancak child’lar kapalı + epic QA comment.

## Scope değişimi

1. Issue body `package_version` artır + `demir-kit` YAML güncelle
2. Audit comment (insan dili özeti)
3. `work-package-amend` skill; gerekirse yeni CP’ler YAML’da

## PR

- `Refs #N` / `Closes #N`

## Orca

- `orca worktree create --issue N` issue-linked worktree
- Automation precheck: `gh issue list --label agent-approved`

## Orca tetik

Label `agent-approved` → coordinator (`orchestration/README.md`).
