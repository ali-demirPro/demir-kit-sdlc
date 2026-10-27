# DevOps — Web

**Capabilities:** `platform.web`, `distribution.web` · **Min level:** expert
**Gate:** `behavior`, `commercial`

## Kapsam

Web build/deploy hattı: preview/prod ayrımı, CDN, cache, secret, rollback ve
SLO.

## Yöntem

1. **Pipeline:** lint → typecheck → test → build → deploy; aşamalar paralel mi?
2. **Environment:** preview/prod/staging; veri ve secret izolasyonu.
3. **Artefakt:** immutable build; aynı artefakt staging→prod.
4. **CDN/cache:** cache key, invalidation, stale-while-revalidate.
5. **Secret:** CI secret, runtime secret, rotasyon; repo'da yok.
6. **Deploy:** atomik/blue-green; health check; trafik geçişi.
7. **Rollback:** önceki build + cache purge; süre hedefi.
8. **Gözlem:** deploy marker, hata oranı, CWV, SLO.

## Kanıt

- Pipeline diff'i ve süreleri.
- Preview URL + prod deploy marker.
- Cache/rollback planı.
- Secret envanteri (değer değil, sahip/rotasyon).
- SLO/alert bağlantısı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Pipeline | Test/build/deploy ayrık |
| Env | Preview/prod izole |
| Artefakt | Immutable |
| Secret | Repo dışı + rotasyon |
| Rollback | Test edilmiş |
| Gözlem | Deploy marker + SLO |

## Anti-pattern'ler

- Prod'a doğrudan `git push`.
- Aynı secret'ı tüm env'lerde kullanmak.
- Cache purge'ü unutmak.
- Rollback'i "yeniden deploy" sanmak.
- Deploy'u ölçmeden "sorunsuz" demek.

## Handoff

Release'e: deploy/rollback kanıtı.
Developer'a: preview + hata logu.
Security'ye: secret/CI izni.
