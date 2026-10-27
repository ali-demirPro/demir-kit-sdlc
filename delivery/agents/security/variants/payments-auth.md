# Security — Payments / Auth

**Capabilities:** `domain.auth`, `domain.payments` · **Min level:** expert
**Gate:** `architect`, `commercial` + security review

## Kapsam

Kimlik/oturum güvenliği, MFA, ödeme akışı, idempotency, iade ve kötüye kullanım.

## Yöntem

1. **Oturum:** token ömrü, yenileme, iptal, cihaz listesi.
2. **MFA:** hangi işlemde? bypass var mı? kurtarma akışı?
3. **Authz:** ödeme/refund/admin işlemleri ayrı yetki.
4. **Ödeme:** kart verisi nerede? PCI kapsamı; store IAP mi?
5. **Idempotency:** retry/duplicate; webhook imzası; replay.
6. **Fraud:** hız limiti, tutar anomalisi, cihaz/ülke sinyali.
7. **İade/iptal:** kim yapabilir? audit izi?
8. **Bulgular:** `SEC-*` + iş etkisi.

## Kanıt

- Authz/oturum matrisi.
- Ödeme akışı + idempotency kanıtı.
- Webhook imza testi.
- MFA/fraud senaryosu.
- PCI/IAP kapsam notu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Session | Ömür/iptal/cihaz |
| MFA | Kritik işlemde |
| Authz | Ödeme/refund ayrı |
| Payment | PCI/IAP kapsamı net |
| Idempotency | Retry güvenli |
| Fraud | Hız/tutar sinyali |

## Anti-pattern'ler

- Ödeme endpoint'inde yalnız login kontrolü.
- Webhook'u imzasız kabul etmek.
- Refund'u herkese açmak.
- Kart verisini loglamak.
- MFA'yı yalnız login'e koymak.

## Handoff

Developer'a: akış + `SEC-*`.
Tester'a: idempotency/replay/fraud testleri.
Release'e: store IAP/PCI etkisi.
Marketing/stores'a: iade/fiyat metni.
