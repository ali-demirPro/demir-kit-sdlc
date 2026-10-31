# PR akışı

`main`'e doğrudan push yerine **epic PR'ı** ile gelinir. Amaç: CI kapısı ve
ikinci göz olmadan `main`'in değişmemesi; aynı epic'in leaf'leri tek worktree ve
tek branch'te toplanır.

## Akış

1. Worktree: epic'in ilk leaf'inde `orca worktree create --name epic-<E> --issue <E>`.
   Branch: `epic-<E>` (Orca'nın ürettiği ad `--json`'dan okunur).
2. Leaf'ler aynı worktree'de sırayla çalışır; her leaf kendi commit'ini ve
   evidence'ını epic branch'ine bırakır. **Leaf başına PR yok.**
3. `leaf-done` main'e merge beklemez; commit epic branch'inde kalır.
4. Tüm leaf'ler kapandığında closure raporu yazılır ve **tek PR** açılır:
   `epic-<E>` → `main`. Başlık: `#<E> <epic başlığı>`.
5. PR için zorunlu kontrol: `delivery-doctor` (test + `doctor.sh --strict`).
   `issue-doctor` PR kontrolü değildir; merge sonrası issue event'lerinde
   `doctor.sh --issue N` çalıştırır.
6. PR yorumunda leaf evidence commit'leri ve CI run'ları linklenir.
7. Yeşilse **merge commit** ile birleştir (squash değil; evidence commit'leri
   geçmişte kalmalı).
8. Merge insan kabulüdür. Ardından:
   `transition.sh --issue E --to epic-done --accept <login>` — merge'i ve temiz
   worktree'yi doğrular, worktree'yi siler (`--keep-worktree` ile korunur).

## Branch koruması

- Rebase yasak; yeni leaf öncesi `git merge origin/main`
  (`epic_worktree.py sync --epic E`). Rebase evidence commit SHA'larını bozar.
- Force push ve branch deletion kapalı.

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
