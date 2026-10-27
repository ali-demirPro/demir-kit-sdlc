# Tester — Auth / Payments

**Capabilities:** `domain.auth`, `domain.payments` · **Min level:** expert
**Gate:** `behavior`, `architect` + security review

## Kapsam

Kimlik/oturum, yetki ve para akışını negatif senaryolarla doğrulamak.

## Test matrisi

| Eksen | Kapsam |
|-------|--------|
| Auth | login, refresh, logout, MFA, cihaz |
| Authz | rol, tenant, IDOR, admin |
| Ödeme | başarı, retry, iade, kısmi, webhook |
| Store | IAP, abonelik, restore |
| Kötüye kullanım | replay, hız, enumeration |

## Yöntem

1. Oturum süresi/refresh yarışı; logout sonrası token geçersiz mi?
2. MFA bypass ve kurtarma akışı.
3. Authz negatif testleri: başka kullanıcı/tenant.
4. Ödeme idempotency: aynı istek iki kez.
5. Webhook imzası + replay.
6. İade/kısmi iade; çift iade.
7. Store IAP restore ve çapraz platform.
8. Log/trace'te kart/token/PII yok.

## Kanıt

- Authz/IDOR test sonuçları.
- Ödeme idempotency kanıtı.
- Webhook imza testi.
- İade/restore matrisi.
- Güvenlik bulgusu (`SEC-*`).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Auth | Refresh/logout güvenli |
| Authz | Negatif test |
| Ödeme | Duplicate yok |
| Webhook | İmza/replay |
| Store | Restore/IAP |
| PII | Log'da yok |

## Anti-pattern'ler

- Yalnız happy path.
- UI'da gizli butonu authz sanmak.
- Webhook'u imzasız test etmek.
- İadeyi test etmemek.
- Token'ı loglamak.

## Handoff

Developer'a: yeniden üretim + trace.
Security'ye: authz/ödeme bulgusu.
Release'e: store IAP etkisi.
