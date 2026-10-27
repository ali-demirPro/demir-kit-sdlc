# Security — Application (Web + API)

**Capabilities:** `platform.web`, `platform.api`, `distribution.web` · **Min level:** expert
**Gate:** `behavior`, `architect` + security review

## Kapsam

Web/API trust boundary, authz, input/output, secret, bağımlılık ve tedarik
zinciri.

## Yöntem

1. **Trust boundary:** browser, edge, API, DB; hangi sınır kime güvenir?
2. **Authz:** endpoint/UI başına yetki; IDOR ve tenant izolasyonu.
3. **Input:** validation, encoding, SSRF, path traversal, upload.
4. **Output:** XSS, güvenli header, CORS, CSP.
5. **Secret:** repo/CI/runtime; rotasyon; log'da sızıntı.
6. **Bağımlılık:** CVE, imza, lockfile, SBOM.
7. **Rate limit/abuse:** brute force, scraping, replay.
8. **Bulgular:** `SEC-*` severity + kanıt + öneri.

## Kanıt

- Threat model + trust boundary.
- Authz matrisi ve IDOR testi.
- SAST/dependency audit sonucu.
- Header/CSP/CORS kontrolü.
- `SEC-*` kapatma kanıtı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Boundary | Trust sınırı çizili |
| Authz | Varsayılan red + tenant |
| Input | Validation/encoding |
| Secret | Sızıntı yok |
| Dependency | Kritik CVE yok |
| Abuse | Rate limit/replay |

## Anti-pattern'ler

- UI'da gizlemeyi authz sanmak.
- `innerHTML` ile kullanıcı verisi.
- Secret'ı env'e koyup repoya da koymak.
- CVE'yi "kullanmıyoruz" diye waive etmek.
- Rate limit'i yalnız login'e koymak.

## Handoff

Developer'a: `SEC-*` + yeniden üretim.
Tester'a: authz/IDOR/abuse senaryoları.
DevOps'a: header/secret/CVE.
Architect'e: boundary/tasarım riski.
