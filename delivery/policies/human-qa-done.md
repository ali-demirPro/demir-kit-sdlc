# human-qa — bitiş çıktısı

Risk modeli C: `low`/`medium` leaf otomatik, `high`/`critical` leaf insan,
**epic kabulü her zaman insan**.

## Leaf human-qa (yalnız `high` / `critical`)

| # | Alan | İçerik |
|---|------|--------|
| 1 | Ne değişti | 2–3 cümle + issue # |
| 2 | Doğrulama | test / CI / manuel adım linki |
| 3 | Kanıt | CP evidence comment linkleri |
| 4 | Follow-up | Açılan child issue # veya "yok" |
| 5 | Risk / rollout | Varsa; yoksa "yok" |
| 6 | Karar | `leaf-done` veya "düzelt #X" |

Label: **`leaf-done`** (epic henüz kapanmaz). `critical` ise ikinci imza.

## Epic human-qa (her zaman)

Epic closure raporu (`runbooks/epic-closure.md`) **geçtikten sonra**:

| # | Alan |
|---|------|
| 1 | Scope tablosu ↔ child issues uyumu |
| 2 | Gap raporu özeti (0 issue veya liste) |
| 3 | Gereksiz / yanlış iş (revert önerisi) |
| 4 | Tüm leaf'ler `leaf-done` veya bilinçli `deferred` |
| 5 | Metrikler (lead time, gate retry, insan müdahalesi) |
| 6 | Karar → **`epic-done`** |

## Şablon (issue comment)

```markdown
## human-qa

**Ne değişti:** …
**Doğrulama:** …
**Kanıt:** …
**Follow-up:** #… / yok
**Risk:** …
**Karar:** leaf-done | epic-done | düzelt #N
```

Türkçe, kısa, jargon yok ([escalation.md](escalation.md)).
