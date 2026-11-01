# Refactor tetikleri

Refactor'u "kodu bir ara temizleriz" işinden çıkarıp planlı, kanıtlı bir leaf'e
çevirir. Kural: refactor **ayrı leaf** açılarak yapılır; mühürsüz refactor yasak
([project-priorities.md](project-priorities.md) P3).

## Ne zaman leaf açılır

Aşağıdakilerden **biri** yeterlidir.

| Tetik | Eşik | Ölçüm |
|-------|------|-------|
| Dosya boyutu | > 600 satır (1000'de zorunlu) | `find . -name '*.py' -o -name '*.swift' \| xargs wc -l \| sort -n \| tail -20` |
| Tip boyutu | Tek tip > 400 satır | `rg -n '^(class\|struct\|enum) ' <dosya>` |
| Yayılma | Bir feature > 6 dosya veya > 2 target | `git show --stat <commit>` |
| Tekrar eden hata | Aynı modülde 3 fix kaydı | `learnings.py --digest` |
| Epic kapanışı | Her closure öncesi zorunlu check-in | `runbooks/epic-closure.md` |
| Test edilemez bağımlılık | Bir bağımlılık testte değiştirilemiyor | test yazmayı dene, takıldığın yeri kaydet |
| Büyük feature öncesi | "Bu feature'ı kolaylaştıracak hangi değişiklik?" | seal notu |

Tetik yoksa refactor leaf'i açılmaz. "Kod hoşuma gitmedi" tetik değildir.

## Kanıt

`verification.refactor` bloğu zorunludur:

```yaml
refactor:
  baseline: { commit: "4f2a1c9", tests: pass, snapshots: "sha256:…" }
  after:    { commit: "9b1e7d3", tests: pass, snapshots: "sha256:…" }
  unchanged: true
  ui_unchanged: true
  files_changed: 7
```

- `baseline`, `after`'ın atası olmalı; aynı commit olamaz.
- İki tarafta da `tests: pass`.
- `unchanged: true` zorunlu — davranış değiştiyse bu bir refactor değildir.
- UI'a dokunulduysa `ui_unchanged: true` ve iki tarafta **eşit** snapshot hash'i.
- `files_changed`: ≤ 10 normal, 11–20 uyarı, > 20 hata (adımlara böl).

## Sınırlar

- Bir adım = bir commit; build her adımda yeşil.
- Feature karışmaz: yeni davranış ayrı leaf.
- Testler değiştirilir, üst üste eklenmez: yeni arayüz testi eskisinin yerini alır.
- Geri dönüşü zor kararlar ADR ister ([CONTRACT.md](../CONTRACT.md)).

## Durma kuralı

Tarama sonucu "kod iyi" olabilir. O zaman kartlar `Speculative` kalır ve leaf
kapatılır; refactor uydurulmaz.
