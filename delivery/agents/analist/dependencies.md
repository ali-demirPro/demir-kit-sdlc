# Dependencies

## Girdiler (zorunlu)

| Kaynak | Ne okunur |
|--------|-----------|
| Epic issue | `scope-confirmed`, body’de scope tablosu veya `scope_triage` |
| Child issues | Başlık, body, `intake` / leaf label’ları |
| Leaf (mühür öncesi) | `reference`, draft `tests_plan`, `entry`, `factory` (ürün kapsamı) |

## Label / durum

- Epic plan: **`scope-confirmed`** (eksikse analist blocker raporu — issue açılana kadar mühür yok).
- Leaf mühür: parent veya leaf’te scope onayı (`scope_triage.confirmed` — legacy issue YAML).
- Closure: tüm leaf **`leaf-done`** veya bilinçli **`deferred`** + kayıt.

## Politikalar

- `delivery/policies/approval.md`
- `delivery/policies/human-qa-done.md` (AC = human-qa girdisi)
- `delivery/runbooks/epic-closure.md` §1

## Legacy (referans)

- `delivery/runbooks/epic-intake.md` — F0–F1 kapsam disiplini (delivery’de analist sürdürür).
- Arşiv (faz 4): `old/references/minimum-viable-output.md` — issue body disiplini.

## Çıktılar

- Issue comment: `## Product analysis` veya `## Scope gap` (şablon `SKILL.md`).
- Önerilen follow-up issue başlıkları (orchestrator veya kullanıcı açar).
