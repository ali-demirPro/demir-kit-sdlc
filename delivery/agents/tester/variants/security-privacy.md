# Tester — Security / Privacy

**Capabilities:** `quality.security`, `quality.privacy` · **Min level:** expert (security) / practitioner (privacy)
**Gate:** `behavior`, `architect` + security/privacy review

## Kapsam

Güvenlik ve gizlilik kontrollerini negatif testlerle doğrulamak.

## Yöntem

1. Authz/IDOR/tenant negatif testleri.
2. Input validation, XSS/SSRF/upload.
3. Secret/CVE/tedarik zinciri kontrolü.
4. Log/trace'te PII/token.
5. Consent/izin reddi.
6. Data retention/silme.
7. Privacy manifest/data safety.
8. Header/CORS/CSP/rate limit.

## Kanıt

- Authz/IDOR sonucu.
- SAST/dependency/CVE.
- PII/consent testi.
- Privacy label kontrolü.
- `SEC-*` kapatma.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Authz | Negatif |
| Input | Encode/validate |
| Secret/CVE | Temiz |
| PII | Log'da yok |
| Consent | Uyumlu |
| Retention | Silme |

## Anti-pattern'ler

- Yalnız happy path.
- CVE'yi "kullanmıyoruz" diye waive.
- Token'ı loglamak.
- Consent'i test etmemek.
- Privacy label'ı okumamak.

## Handoff

Security'ye: bulgu + trace.
Developer'a: fix.
Privacy'ye: data map.
