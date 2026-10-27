# DevOps — API / Service

**Capabilities:** `platform.api`, `platform.cli`, `domain.data` · **Min level:** expert
**Gate:** `behavior`, `architect`

## Kapsam

Servis deploy'u, migration, kuyruk, kapasite, sır yönetimi ve sıfır kesinti.

## Yöntem

1. **Deploy modeli:** rolling/blue-green/canary; sağlık kontrolü.
2. **Migration:** deploy öncesi/sonrası; geri uyumlu şema.
3. **Kuyruk/job:** retry, DLQ, idempotency, backpressure.
4. **Kapasite:** CPU/bellek/bağlantı; autoscale sınırı.
5. **Secret:** runtime injection; rotasyon; erişim izni.
6. **Sıfır kesinti:** drain, readiness, connection pool.
7. **Rollback:** önceki image + şema uyumu.
8. **Gözlem:** latency, hata, doygunluk, migration süresi.

## Kanıt

- Deploy/canary planı.
- Migration sırası ve geri uyumluluk.
- Kuyruk/DLQ ayarı.
- Kapasite ve autoscale.
- Rollback provası.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Deploy | Sağlık + drain |
| Migration | Geri uyumlu |
| Kuyruk | Retry/DLQ |
| Kapasite | Sınır + alarm |
| Secret | Runtime + rotasyon |
| Rollback | Image + şema uyumlu |

## Anti-pattern'ler

- Migration ile kodu aynı anda kırmak.
- Sınırsız retry.
- Connection pool'u yok saymak.
- Canary'yi ölçüsüz geçirmek.
- Secret'ı image'a gömmek.

## Handoff

Data'ya: migration sırası.
Developer'a: deploy/rollback sınırı.
Release'e: sürüm + geri dönüş.
