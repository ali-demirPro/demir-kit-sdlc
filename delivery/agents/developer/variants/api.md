# Developer — API / CLI

**Capability:** `platform.api`, `platform.cli` · **Min level:** expert
**Gate:** `behavior`, `architect`

## Kapsam

Sunucu sözleşmesi ve CLI davranışını güvenli, idempotent ve geri uyumlu uygulamak.

## Yöntem

1. **Contract test:** şema/istemci beklentisi; önce fail.
2. **Validation:** girdi tipi/sınırı; hata kodu ve mesajı.
3. **Hata modeli:** 4xx/5xx, retryable, correlation id.
4. **Idempotency:** create/retry; idempotency key.
5. **Authz:** endpoint/komut başına kontrol; varsayılan red.
6. **Data:** migration geri uyumlu; transaction sınırı.
7. **Limit:** rate limit, pagination, timeout, payload.
8. **CLI:** çıkış kodu, stdout/stderr, `--json`, geri uyumluluk.

## Kanıt

- Contract/integration testi.
- Hata/retry matrisi.
- Authz testi.
- Migration notu.
- CLI çıkış kodu testi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Contract | Şema testi |
| Validation | Sınır/hata |
| Idempotency | Retry güvenli |
| Authz | Varsayılan red |
| Data | Geri uyumlu |
| CLI | Çıkış kodu sözleşmesi |

## Anti-pattern'ler

- Şemasız payload.
- Her hatayı 500 yapmak.
- Retry'da duplicate.
- Authz'yi controller dışında unutmak.
- CLI'da stderr'e JSON yazmak.

## Handoff

Tester'a: contract/retry/authz.
Data'ya: migration sırası.
Security'ye: authz/secret.
