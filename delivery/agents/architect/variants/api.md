# Architect — API / CLI

**Capabilities:** `platform.api`, `platform.cli` · **Min level:** expert
**Gate:** `architect`, `behavior`

## Kapsam

Sunucu sözleşmesi ve komut satırı yüzeyi: sürümleme, hata modeli, idempotency,
yetki, rate limit, geri uyumluluk.

## Yöntem

1. **Sözleşme:** kaynaklar, komutlar, girdi/çıktı; açık şema.
2. **Sürümleme:** breaking change politikası; deprecation penceresi.
3. **Hata modeli:** kod, mesaj, retryable, correlation id.
4. **Idempotency:** create/retry/duplicate; idempotency key.
5. **Yetki:** endpoint/komut başına authz; varsayılan red.
6. **Limitler:** rate limit, pagination, timeout, payload boyutu.
7. **CLI:** çıkış kodu, stdout/stderr ayrımı, `--json`, geri uyumluluk.
8. **Gözlemlenebilirlik:** request id, latency, hata oranı.

## Kanıt

- API/CLI sözleşme dokümanı veya şeması.
- Hata/retry matrisi.
- Authz matrisi.
- Sürüm/deprecation planı.
- Contract test listesi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Sözleşme | Şema/açıklama tam |
| Sürüm | Breaking change politikası var |
| Hata | Retryable ayrımı net |
| Idempotency | Retry güvenli |
| Authz | Varsayılan red |
| CLI | Çıkış kodu/stdout sözleşmesi |

## Anti-pattern'ler

- Şemasız "JSON döner" API.
- Her hatayı 500 yapmak.
- Retry'da duplicate yaratmak.
- Authz'yi UI'a bırakmak.
- CLI'da çıkış kodunu rastgele seçmek.

## Handoff

Developer'a: sözleşme + hata matrisi.
Tester'a: contract/retry/authz testleri.
Security'ye: authz ve veri sınırı.
