# Tester — A11y / Performance

**Capabilities:** `quality.a11y`, `quality.performance` · **Min level:** expert
**Gate:** `behavior`, `ui`

## Kapsam

Erişilebilirlik ve performansı ölçülebilir şekilde doğrulamak.

## Yöntem

1. Klavye turu: tüm akış, focus, tuzak.
2. VoiceOver/TalkBack: sıra/label/action.
3. Kontrast ve font scale 2.0.
4. Reduced motion.
5. CWV: LCP/INP/CLS.
6. p95/startup/bellek.
7. Yük/yoğunluk; üçüncü parti.
8. Regresyon: baseline screenshot/ölçüm.

## Kanıt

- A11y audit + focus sırası.
- Cihaz/font scale screenshot'ı.
- CWV/p95 ölçümü.
- Baseline karşılaştırması.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Klavye | Tüm akış |
| SR | Anlamlı |
| Kontrast | AA |
| Font | 2.0 |
| CWV | Budget |
| p95 | Budget |

## Anti-pattern'ler

- Yalnız axe/otomatik test.
- Tek cihazda performans.
- Font scale atlamak.
- Baseline'sız regresyon.
- Yavaşlığı "kabul" saymak.

## Handoff

Developer'a: ölçüm + trace.
Designer'a: a11y/font.
DevOps'a: SLO.
