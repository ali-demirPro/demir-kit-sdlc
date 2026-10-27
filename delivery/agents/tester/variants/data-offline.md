# Tester — Data / Offline

**Capabilities:** `domain.data`, `domain.offline` · **Min level:** expert
**Gate:** `behavior`, `architect`

## Kapsam

Migration, backfill, rollback ve offline senkronizasyonun veri bütünlüğü.

## Test matrisi

| Eksen | Kapsam |
|-------|--------|
| Migration | ileri/geri, kilit, süre |
| Backfill | batch, hata, tekrar |
| Rollback | veri kaybı, sürüm uyumu |
| Offline | kuyruk, replay, çakışma |
| Lifecycle | process death, restore |
| Veri | şema, null, kısmi kayıt |

## Yöntem

1. Migration dry-run; süre/kilit ölç.
2. Backfill'i iki kez koş; duplicate yok.
3. Rollback sonrası eski kod çalışıyor mu?
4. Offline'da işlem kuyruğa giriyor mu?
5. Ağ dönünce replay; sıra/idempotency.
6. Çakışma politikası: son-yazan mı, merge mi?
7. Process death sonrası state/kuyruk korunuyor mu?
8. Kısmi kayıt/tutarlılık kontrolü.

## Kanıt

- Migration/backfill test sonucu.
- Rollback smoke.
- Offline replay/conflict kanıtı.
- Process death testi.
- Veri doğrulama sorgusu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Migration | İleri/geri |
| Backfill | Idempotent |
| Rollback | Veri kaybı yok |
| Offline | Kuyruk/replay |
| Conflict | Politika test |
| Integrity | Tutarlı |

## Anti-pattern'ler

- Migration'ı prod'da ilk kez denemek.
- Backfill'i tekrar güvenli sanmak.
- Offline'da last-write-wins varsayımı.
- Process death'i atlamak.
- Rollback'i "yeniden deploy" sanmak.

## Handoff

Data'ya: migration/backfill.
Developer'a: conflict/replay.
DevOps'a: kilit/süre/rollback.
