# Architect — Data / Offline

**Capabilities:** `domain.data`, `domain.offline` · **Min level:** expert
**Gate:** `architect`, `behavior`

## Kapsam

Veri modeli, migration, backfill, offline senkronizasyon ve çakışma çözümü.

## Yöntem

1. **Model:** entity, ilişki, sahiplik, yaşam döngüsü.
2. **Migration:** ileri/geri adım; idempotency; kilit ve süre.
3. **Backfill:** hacim, batch, hata, tekrar güvenliği.
4. **Rollback:** veri kaybı olmadan geri dönüş mümkün mü?
5. **Offline:** kaynak-of-truth, kuyruk, replay, çakışma politikası.
6. **Retention:** saklama, silme, anonimleştirme.
7. **Analytics:** event şeması ve türetilmiş metrik.
8. **NFR:** veri hacmi, gecikme, tutarlılık.

## Kanıt

- ER/şema diyagramı.
- Migration + rollback planı; dry-run.
- Backfill runbook'u.
- Çakışma matrisi.
- Retention/data map.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Model | Sahiplik ve ilişki net |
| Migration | İleri/geri + idempotent |
| Backfill | Batch/hata planı |
| Rollback | Veri kaybı yok |
| Offline | Çakışma politikası |
| Retention | Saklama/silme tanımlı |

## Anti-pattern'ler

- Geri dönüşsüz migration.
- Tek seferde milyonlarca satır backfill.
- Offline'da son-yazan-kazanır varsayımı.
- Retention'ı hukuk ekibine bırakmak.
- Analitik event'i sonradan uydurmak.

## Handoff

Data'ya: migration/backfill planı.
Developer'a: model + offline state.
Tester'a: migration/rollback/çakışma testleri.
Security/Privacy'ye: veri sınıflandırma ve retention.
