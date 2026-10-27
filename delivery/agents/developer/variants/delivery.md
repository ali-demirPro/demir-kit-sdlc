# Developer — Delivery

**Capability:** `distribution.web` · **Min level:** practitioner
**Gate:** `behavior`, `commercial`

## Kapsam

Kodun güvenli şekilde prod'a çıkması: build, flag, deploy ve geri dönüş.

## Yöntem

1. **Build:** aynı artefakt staging→prod; versiyon/commit işaretli.
2. **Feature flag:** karanlık launch; kill switch.
3. **Deploy:** sağlık kontrolü; kademeli trafik.
4. **Migration:** kod ile geri uyumlu; ayrı adım.
5. **Gözlem:** deploy marker, hata oranı, latency.
6. **Rollback:** flag kapat / önceki artefakt; süre hedefi.
7. **Kanıt:** deploy logu, marker, smoke.

## Kanıt

- Build/commit izlenebilirliği.
- Flag/deploy planı.
- Smoke sonucu.
- Rollback adımı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Build | Immutable + izlenebilir |
| Flag | Kill switch |
| Deploy | Sağlık + kademeli |
| Migration | Geri uyumlu |
| Rollback | Test edilmiş |

## Anti-pattern'ler

- Flag'siz büyük değişiklik.
- Migration ile kodu aynı anda kırmak.
- Smoke'suz deploy.
- Rollback'i "yeniden deploy" sanmak.

## Handoff

DevOps'a: deploy/rollback.
Release'e: sürüm notu.
