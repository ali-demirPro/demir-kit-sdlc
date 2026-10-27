# DevOps — Observability / Quality

**Capabilities:** `quality.observability`, `quality.performance`, `quality.security`, `quality.privacy` · **Min level:** expert
**Gate:** `behavior`, `architect`

## Kapsam

Log/metric/trace, SLO, alarm, kapasite, maliyet ve güvenlik/privacy sinyalleri.

## Yöntem

1. **Telemetry:** yapılandırılmış log, metric, trace; correlation id.
2. **SLO:** kullanıcı odaklı gösterge; hata bütçesi; burn-rate alarmı.
3. **Alarm:** eşik, sahiplik, runbook, gürültü bütçesi.
4. **Dashboard:** deploy marker, hata, latency, doygunluk.
5. **PII:** log'da maskeleme; saklama süresi.
6. **Güvenlik sinyali:** auth fail, rate limit, anormal erişim.
7. **Maliyet:** kartinality, retention, gereksiz trace.
8. **Tatbikat:** alarm→runbook→rollback.

## Kanıt

- SLO/alert tanımı.
- Dashboard ekranı/linki.
- Log/trace örneği + PII kontrolü.
- Runbook.
- Maliyet/retention notu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| SLO | Gösterge + bütçe |
| Alarm | Eşik + sahip |
| Telemetry | Log/metric/trace |
| PII | Maskeli |
| Güvenlik | Anomali sinyali |
| Maliyet | Retention/kardinalite |

## Anti-pattern'ler

- Her şeyi loglamak.
- Sahipsiz alarm.
- SLO'yu CPU ile ölçmek.
- PII'yi log'a yazmak.
- Trace'i süresiz saklamak.

## Handoff

Architect'e: NFR/SLO geri bildirimi.
Developer'a: telemetry noktaları.
Security'ye: anomali sinyali.
Release'e: deploy marker.
