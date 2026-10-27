# Designer — Analytics

**Capability:** `domain.analytics` · **Min level:** aware
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Kapsam

Tasarımın ölçülebilir olması: event, funnel, guardrail ve PII sınırı.

## Yöntem

1. **Karar:** hangi tasarım kararı hangi metrikle ölçülecek?
2. **Event:** kullanıcı eylemi başına tek anlamlı event.
3. **Funnel:** adım tanımı; drop-off noktası.
4. **Guardrail:** dönüşüm artarken bozulmaması gereken metrik.
5. **PII:** event/property'de kişisel veri yok.
6. **Consent:** ölçüm izinle; red edilince çalışır.
7. **Dashboard:** tasarım ekibi için okunur tek ekran.
8. **Test:** event adı/şeması developer ile aynı.

## Kanıt

- Event/funnel tanımı.
- Guardrail metriği.
- PII kontrolü.
- Consent notu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Karar | Metrik bağlı |
| Event | Tek anlam |
| Funnel | Adımlar net |
| Guardrail | Tanımlı |
| PII | Yok |
| Consent | Uyumlu |

## Anti-pattern'ler

- Her tıklamayı event yapmak.
- Event adını sonra değiştirmek.
- PII'yi property'ye koymak.
- Guardrail'siz deney.
- Consent'siz ölçüm.

## Handoff

Growth/run'a: funnel/deney.
Developer'a: event şeması.
Privacy'ye: veri sınırı.
