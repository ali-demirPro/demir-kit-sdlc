# Security — Data / Privacy

**Capabilities:** `domain.data`, `quality.privacy` · **Min level:** expert
**Gate:** `architect`, `commercial` + privacy review

## Kapsam

Veri sınıflandırma, minimizasyon, saklama, silme, consent ve migration'ın
gizlilik etkisi.

## Yöntem

1. **Data map:** hangi veri, nerede, kim erişir, ne kadar kalır?
2. **Sınıflandırma:** public/internal/confidential/secret; PII/özel nitelikli.
3. **Minimizasyon:** alan gerçekten gerekli mi? türetilebilir mi?
4. **Saklama/silme:** retention, hard delete, anonimleştirme.
5. **Consent:** toplama amacı, ATT/izin, geri çekme.
6. **Migration:** yeni alan/tablo privacy etkisi; backfill.
7. **Üçüncü parti:** processor, transfer, DPA.
8. **Bulgular:** `PRIV-*`/`SEC-*` + hukuki risk.

## Kanıt

- Data map + sınıflandırma.
- Retention/silme planı.
- Consent akışı.
- Privacy manifest/data safety.
- Migration privacy etkisi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Data map | Alan/amaç/sahip |
| Minimize | Gereksiz alan yok |
| Retention | Süre + silme |
| Consent | Amaç + geri çekme |
| Migration | Privacy etkisi |
| Üçüncü parti | Processor/transfer |

## Anti-pattern'ler

- "Sonra sileriz" demiş olmak.
- PII'yi analytics'e göndermek.
- Consent'i karanlık desenle almak.
- Retention'ı sonsuz bırakmak.
- Migration'da privacy etkisini atlamak.

## Handoff

Data'ya: retention/silme.
Developer'a: minimize/consent.
Release'e: manifest/data safety.
Architect'e: veri akışı.
