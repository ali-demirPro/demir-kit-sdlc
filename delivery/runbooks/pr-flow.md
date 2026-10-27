# PR akışı

`main`'e doğrudan push yerine her kaynak değişikliği PR ile gelir. Amaç: CI
kapısı ve ikinci göz olmadan `main`'in değişmemesi.

## Akış

1. Branch: `leaf-<N>-<kısa-ad>`.
2. PR başlığı: `#<N> <kısa başlık>`; gövde şablonu otomatik gelir.
3. PR için zorunlu kontrol: `delivery-doctor` (test + `doctor.sh --strict`).
   `issue-doctor` PR kontrolü değildir; merge sonrası issue event'lerinde
   `doctor.sh --issue N` çalıştırır.
4. PR yorumunda evidence commit'i ve CI run'ı linklenir.
5. Yeşilse **merge commit** ile birleştir (squash değil; evidence commit'i
   geçmişte kalmalı).
6. Merge sonrası `transition.sh --issue N --to leaf-done`; issue-doctor
   evidence commit'ini `main` üzerinde görebilsin.
7. `doctor.sh --issue N` bir kez daha çalıştırılır.

## Branch protection

Koruma kodla uygulanır:

```bash
./delivery/scripts/protect_main.sh --apply
./delivery/scripts/protect_main.sh --check
```

- PR zorunlu.
- Required check: `delivery-doctor`.
- `enforce_admins: true`; admin bypass kapalı.
- Force push ve branch deletion kapalı.
- `issue-doctor` PR gate'i değildir; merge sonrası issue doğrulamasıdır.

## Rollback

Merge geri alınır (`git revert -m 1 <merge>`), issue `blocked` + `epic-reconcile`
ile işaretlenir; yeni leaf açılır. Geçmiş evidence silinmez.
