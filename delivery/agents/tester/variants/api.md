# Tester — API / CLI

**Capabilities:** `platform.api`, `platform.cli` · **Min level:** expert
**Gate:** `behavior`, `architect`

## Kapsam

Sözleşme, hata, idempotency, authz, limit ve CLI davranışını doğrulamak.

## Test matrisi

| Eksen | Kapsam |
|-------|--------|
| Contract | Şema/istemci uyumu, breaking change |
| Hata | 4xx/5xx, retryable, correlation id |
| Idempotency | Aynı istek/retry, duplicate |
| Authz | Rol/tenant, IDOR |
| Limit | Rate limit, pagination, timeout |
| CLI | Çıkış kodu, stdout/stderr, `--json` |

## Yöntem

1. AC'yi contract/integration case'ine çevir.
2. Şema doğrulaması + geri uyumluluk kontrolü.
3. Retry/duplicate senaryosu; yan etki tek mi?
4. Authz negatif testleri (başka tenant/rol).
5. Rate limit/timeout; hata mesajı sızıntısı.
6. CLI çıkış kodu/stdout sözleşmesi.
7. Migration/rollback smoke (varsa).
8. Log/trace'te PII ve secret kontrolü.

## Kanıt

- Contract/integration sonucu.
- Hata/retry matrisi.
- Authz negatif testleri.
- CLI çıkış kodu testi.
- Trace/log örneği.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Contract | Şema + geri uyumluluk |
| Hata | Retryable ayrımı |
| Idempotency | Duplicate yok |
| Authz | Negatif test |
| Limit | Rate/timeout |
| CLI | Çıkış kodu sözleşmesi |

## Anti-pattern'ler

- Yalnız happy path.
- Authz'yi UI'da test etmek.
- Retry'da duplicate kontrolü yapmamak.
- CLI çıkış kodunu yok saymak.
- Log'da token/email bırakmak.

## Handoff

Developer'a: contract/retry/authz.
Architect'e: breaking change.
Security'ye: authz/secret.
