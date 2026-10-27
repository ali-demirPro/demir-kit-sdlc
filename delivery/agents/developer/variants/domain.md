# Developer — Domain (Auth, Payments, Data, Offline, i18n, Analytics)

**Capabilities:** `domain.auth`, `domain.payments`, `domain.data`, `domain.offline`, `domain.i18n`, `domain.analytics` · **Min level:** practitioner
**Gate:** `behavior`, `architect`

## Kapsam

Domain davranışını güvenli varsayılanlarla uygulamak; özel akışlarda architect/security ile hizalanmak.

## Auth

- Token/session saklama; refresh yarışı; logout her yerde.
- Authz'yi server'da uygula; UI'da gizleme yetki değildir.
- Hata mesajı kullanıcı numaralandırmasını açığa çıkarmasın.

## Payments

- Idempotency key; retry'da çift çekim yok.
- Webhook imzası + replay koruması.
- Store IAP akışı ile kendi ödeme akışını karıştırma.

## Data

- İleri/geri migration; idempotent backfill.
- Transaction sınırı; kilit ve süre.
- Rollback veri kaybı olmadan.

## Offline

- Kuyruk + replay; çakışma politikası.
- Kullanıcıya "bekliyor/senkron" durumu göster.
- Aynı işlemi iki kez uygulama.

## i18n

- Hardcoded metin yok; locale para/tarih/sayı.
- Çoğul/eril; RTL; uzun çeviri taşması.
- Pseudo-locale testi.

## Analytics

- Event adı/şeması sabit; PII yok.
- Kritik funnel'da tek event; duplicate yok.
- Hata/retry event'i ayrı.

## Kanıt

- Domain testleri (authz/idempotency/migration/conflict).
- Locale/analytics şema testi.
- Rollback/backfill notu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Auth | Server authz + güvenli oturum |
| Payments | Idempotent + imzalı webhook |
| Data | Geri uyumlu migration + rollback |
| Offline | Kuyruk + çakışma politikası |
| i18n | Locale kaynağı + taşma testi |
| Analytics | Şema + PII yok |

## Anti-pattern'ler

- Client-side authz.
- Webhook'u doğrulamadan işlemek.
- Offline'da last-write-wins varsayımı.
- Kullanıcı metnini kod içine gömmek.
- Analytics'e email/kullanıcı adı göndermek.

## Handoff

Architect/Security'ye: akış riski.
Tester'a: domain senaryoları.
Data'ya: migration/backfill.
