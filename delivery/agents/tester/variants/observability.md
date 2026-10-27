# Tester — Observability

**Capability:** `quality.observability` · **Min level:** practitioner
**Gate:** `behavior`

## Kapsam

Log/metric/trace ve SLO/alarm davranışını doğrulamak.

## Yöntem

1. Hata yolu log'u: yeterli bağlam, PII yok.
2. Metric: doğru label, kardinalite.
3. Trace: kritik akışta span, correlation id.
4. SLO: gösterge doğru mu?
5. Alarm: eşik + runbook.
6. Deploy marker.
7. Retry/timeout log'u.
8. Dashboard erişimi.

## Kanıt

- Log/trace örneği.
- Metric/alert testi.
- SLO hesabı.
- Runbook linki.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Log | Bağlam + PII yok |
| Metric | Doğru label |
| Trace | Span/correlation |
| SLO | Doğru |
| Alarm | Eşik/runbook |
| Dashboard | Erişilir |

## Anti-pattern'ler

- Log'suz hata.
- PII loglamak.
- Sahipsiz alarm.
- SLO'yu CPU ile ölçmek.
- Trace'i yalnız prod'da açmak.

## Handoff

DevOps'a: alert/runbook.
Developer'a: telemetry.
