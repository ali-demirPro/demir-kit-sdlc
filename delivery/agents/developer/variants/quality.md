# Developer — Quality (Security, Privacy, A11y, Performance, Observability)

**Capabilities:** `quality.security`, `quality.privacy`, `quality.a11y`, `quality.performance`, `quality.observability` · **Min level:** practitioner
**Gate:** `behavior`

## Kapsam

Kodun güvenli, gizliliğe uygun, erişilebilir, hızlı ve gözlemlenebilir olması.

## Security

- Girdiyi validate et, çıktıyı encode et.
- Secret'ı kod/log/CI'a koyma; parametre/env kullan.
- Authz her endpoint'te; varsayılan red.
- Bağımlılık eklerken CVE/lisans kontrolü.

## Privacy

- Yalnız gerekli veriyi topla; log'da PII yok.
- Analytics event'inde kişisel veri yok.
- Silme/retention akışını bozma.

## A11y

- Semantic element, label, focus sırası.
- Klavye ile tam akış; `aria-live` hata.
- Kontrast ve dokunma hedefi.

## Performance

- Bütçe: bundle, sorgu, render, startup.
- N+1, gereksiz re-render, büyük asset yok.
- Ölçüm: CWV/p95/startup.

## Observability

- Anlamlı log + correlation id; PII yok.
- Metric/trace kritik yolda.
- Hata sessiz yutulmaz.

## Kanıt

- Lint/SAST/bağımlılık çıktısı.
- A11y/focus testi.
- Performans ölçümü.
- Log/trace örneği.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Security | Encode/authz/secret |
| Privacy | Minimize + log'da PII yok |
| A11y | Semantik/focus/kontrast |
| Performance | Bütçe içinde |
| Observability | Log/metric/trace + correlation |

## Anti-pattern'ler

- `eval`/`innerHTML` ile kullanıcı verisi.
- PII'yi log'a yazmak.
- `outline: none`.
- Ölçümsüz "optimize" etmek.
- Hatayı `catch {}` ile yutmak.

## Handoff

Security/Privacy'ye: riskli akış.
Tester'a: a11y/perf senaryoları.
DevOps'a: telemetry noktaları.
