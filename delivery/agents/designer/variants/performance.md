# Designer — Performance

**Capability:** `quality.performance` · **Min level:** practitioner
**Packs:** `web-ux`
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Kapsam

Algılanan ve ölçülen performansı tasarım kararına bağlamak: LCP/INP/CLS,
asset bütçesi, font, görsel ve hareket.

## Yöntem

1. **Bütçe:** sayfa başına JS/CSS/görsel/font üst sınırı.
2. **LCP:** hero görsel/metin; boyut, format, priority.
3. **CLS:** sabit alan, skeleton boyutu, font swap stratejisi.
4. **INP:** ağır etkileşim; optimistic/feedback tasarımı.
5. **Görsel:** WebP/AVIF, srcset, lazy; dekoratif görselde boş alt.
6. **Font:** subset, `font-display`, sistem fallback.
7. **Hareket:** 60fps hedefi; layout tetikleyen animasyon yok.
8. **Mobil:** startup, bellek, pil; ağır blurlar.

## Kanıt

- Bütçe tablosu.
- LCP/CLS/INP ölçümü veya tahmini.
- Asset/font stratejisi.
- Ağır etkileşim notu.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Bütçe | Tanımlı |
| LCP | Aday + strateji |
| CLS | Sabit alan |
| INP | Etkileşim bütçesi |
| Asset | Format/boyut |
| Mobil | Startup/bellek |

## Anti-pattern'ler

- Hero'ya 2MB görsel.
- Tüm font ailelerini yüklemek.
- Layout shift üreten skeleton.
- Sınırsız animasyon.
- "İyi görünüyorsa hızlıdır" demek.

## Handoff

Developer'a: asset/font/ölçü.
Tester'a: CWV/latency senaryosu.
