# Architect — Security (Auth, Payments, Threat)

**Capabilities:** `domain.auth`, `domain.payments`, `quality.security` · **Min level:** expert
**Gate:** `architect` + security review

## Kapsam

Trust boundary, kimlik/oturum, yetki, ödeme akışı, secret ve tedarik zinciri
kararları.

## Yöntem

1. **Trust boundary:** hangi bileşen kime güvenir? Ağ sınırı nerede?
2. **Kimlik/oturum:** token, süre, yenileme, iptal, cihaz güveni.
3. **Authz:** rol/izin matrisi; varsayılan red; tenant izolasyonu.
4. **Ödeme:** akış, idempotency, iade, webhook imzası, store IAP kuralları.
5. **Secret:** nerede saklanır, kim erişir, rotasyon?
6. **Tedarik zinciri:** bağımlılık, imza, CI izni, SBOM ihtiyacı.
7. **Tehdit modeli:** STRIDE + kötüye kullanım senaryosu.
8. **Karar:** risk kabulü gerekiyorsa insana bırak; ADR'ye yaz.

## Kanıt

- Threat model + trust boundary diyagramı.
- Authz matrisi.
- Ödeme/idempotency akışı.
- Secret/rotation planı.
- `SEC-*` bulguları ve kapatma kanıtı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Boundary | Trust sınırı çizili |
| Authz | Varsayılan red + tenant |
| Ödeme | Idempotent + iade |
| Secret | Saklama/rotasyon |
| Supply chain | Bağımlılık görünür |
| Threat | En az 5 senaryo |

## Anti-pattern'ler

- UI'da gizlenen butonu yetki sanmak.
- Ödeme webhook'unu imzasız kabul etmek.
- Secret'ı repo/env dışında dağınık tutmak.
- Threat model'i "kütüphane var" diye geçmek.
- Risk kabulünü agent'a yıkmak.

## Handoff

Security'ye: threat model + authz matrisi.
Developer'a: sınır ve ödeme akışı.
Tester'a: authz/ödeme senaryoları.
Release'e: store/privacy etkisi.
