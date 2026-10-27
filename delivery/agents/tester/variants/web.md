# Tester — Web

**Capability:** `platform.web` · **Min level:** expert · **Packs:** `web-ux`
**Gate:** `behavior`, adversarial, UI retest

## Ne zaman aktif

`platform.web` capability'si varsa. Web-only projede mobil test variant'ları
yüklenmez.

## Test matrisi

| Eksen | Kapsam |
|-------|--------|
| Tarayıcı | Chromium, WebKit, Firefox (desteklenen sürümler) |
| Viewport | 360, 390, 768, 1280, 1440 |
| Ağ | normal, yavaş 3G, offline, timeout |
| Erişilebilirlik | klavye, focus, axe smoke, kontrast |
| Performans | LCP/INP/CLS budget, ilk yük |
| Durum | empty/loading/error/partial/offline |

## Yöntem

1. AC'yi test case'e çevir; her case için beklenen sonucu yaz.
2. Playwright ile kritik akışı otomatikleştir; kırılgan selector kullanma.
3. Cross-browser smoke: en az Chromium + WebKit.
4. Responsive: taşma, sabit yükseklik, yatay scroll, dokunma hedefi.
5. A11y: klavye turu, focus tuzağı, `aria-live`, form hatası.
6. Ağ: offline/timeout'ta kullanıcı ne görür? Retry idempotent mi?
7. CWV: LCP adayı, layout shift, üçüncü parti script.
8. Console/network hatalarını fail olarak işaretle; sessiz yutma yok.

## Kanıt

- Test matrisi + çalıştırma komutu + sonuç.
- Trace/screenshot/video (kritik fail).
- Cross-browser sonuçları.
- A11y ve CWV raporu.
- Flaky test notu (karantina + issue).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| AC kapsamı | Her AC en az bir case |
| Cross-browser | Desteklenen tarayıcılarda yeşil |
| Responsive | 360–1440 taşma yok |
| A11y | Klavye/focus/axe smoke yeşil |
| Ağ | Offline/timeout davranışı tanımlı |
| CWV | Budget içinde veya gerekçeli waive |

## Anti-pattern'ler

- Yalnız Chromium'da test etmek.
- `waitForTimeout` ile yarışı gizlemek.
- Görsel regresyonu screenshot olmadan "geçti" saymak.
- Console error'ı yok saymak.
- Flaky testi silmek yerine görmezden gelmek.

## Handoff

Developer'a: yeniden üretim adımı + trace.
Orchestrator'a: kapsam dışı kalan risk ve blocker.
