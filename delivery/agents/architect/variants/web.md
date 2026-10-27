# Architect — Web

**Capabilities:** `platform.web` · **Min level:** expert
**Gate:** `architect`, `behavior`

## Kapsam

Tarayıcı ürününün sınırları: rendering stratejisi, veri akışı, caching, API
sözleşmesi, hata modları ve NFR'ler.

## Yöntem

1. **Bağlam:** kullanıcı akışı, surface sınırı, dış bağımlılıklar.
2. **Boundary:** client/server/edge; hangi veri nerede yaşar?
3. **Rendering:** SSR/CSR/ISR/static; SEO, auth ve tazelik ile gerekçele.
4. **Veri akışı:** cache, invalidation, optimistic update, hata/retry.
5. **NFR:** LCP/INP, erişilebilirlik, ölçek, maliyet, güvenlik.
6. **Hata modları:** API down, stale cache, kısmi yükleme, offline.
7. **Tradeoff:** en az iki alternatif; seçimi ADR'ye yaz.
8. **CP DAG:** boundary ve risk sırasına göre bağımlılık.

## Kanıt

- `ADR-*`: bağlam, alternatifler, karar, sonuç.
- Boundary/veri akışı diyagramı.
- NFR tablosu + ölçüm planı.
- Risk kaydı: SPOF, cache, üçüncü parti.
- `AR-*` bulguları (varsa).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Boundary | Sorumluluklar tek anlamlı |
| Rendering | Gerekçeli; SEO/auth ile çelişmiyor |
| NFR | Ölçülebilir hedef var |
| Hata modu | En az 3 senaryo tasarlanmış |
| Tradeoff | Alternatif + geri dönüş planı |
| CP DAG | Bağımlılık ve risk sıralı |

## Anti-pattern'ler

- "Her şey client'ta" veya "her şey SSR" varsayımı.
- Cache invalidation'ı görmezden gelmek.
- NFR'yi "sonra bakarız" demek.
- Tek alternatifli ADR.
- UI detayına mimar olarak karar vermek.

## Handoff

Developer'a: boundary + ADR + CP DAG.
Tester'a: hata modu matrisi ve NFR ölçümü.
Security'ye: trust boundary ve veri akışı.
