# Developer — Web

**Capability:** `platform.web` · **Min level:** expert
**Gate:** `behavior`, UI retest

## Kapsam

Tarayıcı uygulamasında küçük, test edilebilir ve geri alınabilir değişiklik.

## Yöntem

1. **Kırmızı test:** AC'yi Playwright/unit case'e çevir; önce fail gör.
2. **Sınır:** component/service ayrımı; state'i tek yerde tut.
3. **State:** loading/empty/error/partial/offline; retry idempotent mi?
4. **Form:** validation, hata eşlemesi, klavye, autofill, çift submit.
5. **Erişilebilirlik:** semantic HTML, focus, `aria-live`, kontrast.
6. **Performans:** bundle etkisi, LCP adayı, gereksiz render.
7. **Güvenlik:** kullanıcı verisini encode et; secret client'a koyma.
8. **Kanıt:** kırmızı→yeşil, lint/typecheck, screenshot/trace.

## Kanıt

- Test diff'i (red→green).
- Lint/typecheck çıktısı.
- Etkilenen ekran görüntüsü/trace.
- Bundle/CWV notu (UI ise).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Test | AC'yi kapsayan kırmızı→yeşil |
| State | Hata/empty/loading |
| A11y | Semantic + focus |
| Güvenlik | Encode/secret yok |
| Diff | Minimal ve geri alınabilir |
| Kanıt | Komut + çıktı |

## Anti-pattern'ler

- Testi sonra yazmak.
- `any`/`ts-ignore` ile tipi susturmak.
- Kapsam dışı refactor.
- Secret'ı client bundle'a koymak.
- Console error bırakmak.

## Handoff

Tester'a: çalıştırma komutu + trace.
Architect'e: boundary ihlali/ADR ihtiyacı.
