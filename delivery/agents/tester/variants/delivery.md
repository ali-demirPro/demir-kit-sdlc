# Tester — Delivery

**Capability:** `distribution.web` · **Min level:** practitioner
**Gate:** `behavior`, `commercial`

## Kapsam

Web deploy'un güvenli çıktığını ve geri dönebildiğini doğrulamak.

## Yöntem

1. Preview build smoke.
2. Prod deploy marker + sağlık.
3. Cache/CDN invalidation.
4. Feature flag aç/kapat.
5. Migration/code uyumu.
6. Rollback tatbikatı.
7. CWV/error rate deploy sonrası.
8. Smoke: kritik akış.

## Kanıt

- Preview URL + smoke.
- Deploy marker.
- Flag/rollback testi.
- Hata oranı/CWV.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Preview | Smoke |
| Deploy | Marker |
| Cache | Purge |
| Flag | Kill switch |
| Rollback | Çalışır |
| Post-deploy | SLO |

## Anti-pattern'ler

- Preview'sız prod.
- Cache purge'süz deploy.
- Flag'siz büyük değişiklik.
- Rollback denememek.
- Deploy sonrası ölçmemek.

## Handoff

DevOps'a: rollback/smoke.
Release'e: deploy kanıtı.
