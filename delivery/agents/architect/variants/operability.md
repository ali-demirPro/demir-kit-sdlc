# Architect — Operability (Performance, Privacy, Observability)

**Capabilities:** `quality.performance`, `quality.privacy`, `quality.observability` · **Min level:** practitioner
**Gate:** `architect`, `behavior`

## Kapsam

NFR'lerin ölçülebilir hale gelmesi: SLO, telemetry, performans bütçesi, maliyet
ve privacy sinyalleri.

## Yöntem

1. **NFR:** p95 latency, hata oranı, startup, CWV, maliyet hedefi.
2. **SLO:** kullanıcı odaklı gösterge; hata bütçesi.
3. **Telemetry:** log/metric/trace; correlation id; PII ayıklama.
4. **Alarm:** eşik, sahiplik, runbook; gürültü bütçesi.
5. **Performans bütçesi:** bundle, sorgu, cache, üçüncü parti.
6. **Privacy:** veri minimizasyonu, saklama, log'da PII.
7. **Maliyet:** kapasite, kuyruk, gereksiz çağrı.
8. **Karar:** ölçüm yoksa "iyi" deme; ölçüm planı yaz.

## Kanıt

- NFR/SLO tablosu.
- Dashboard/alert taslağı.
- Log/trace örneği; PII kontrolü.
- Performans bütçesi.
- Maliyet tahmini.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| NFR | Ölçülebilir hedef |
| SLO | Gösterge + hata bütçesi |
| Telemetry | Log/metric/trace bağlı |
| Alarm | Eşik + runbook |
| Privacy | Log'da PII yok |
| Maliyet | Kapasite tahmini |

## Anti-pattern'ler

- "Hızlı olacak" demek; ölçüm yok.
- Her şeyi loglamak; PII sızdırmak.
- Alarmı sahipsiz bırakmak.
- SLO'yu vanity metric yapmak.
- Performansı yalnız prod'da görmek.

## Handoff

DevOps'a: SLO/alert/runbook.
Developer'a: bütçe ve telemetry noktaları.
Privacy/Security'ye: veri akışı ve PII.
