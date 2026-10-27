# Marketing / Landing — Landing

**Capabilities:** `platform.web`, `quality.a11y`, `distribution.web` · **Min level:** expert (web) / practitioner
**Gate:** `commercial`, `ui_visual`, `ui_interaction`

## Kapsam

Landing sayfasının değer önerisi, dönüşüm akışı, erişilebilirliği ve yayını.

## Yöntem

1. **Değer önerisi:** 5 saniyede anlaşılır başlık + alt başlık + CTA.
2. **Akış:** hero → kanıt → özellik → fiyat → SSS → CTA; tek ana eylem.
3. **Sosyal kanıt:** logo, metrik, referans; abartı yok.
4. **Form:** minimum alan; hata/başarı; gizlilik metni.
5. **A11y:** semantik, kontrast, focus, klavye.
6. **Performans:** LCP/CLS/INP; ağır asset yok.
7. **Analytics:** CTA click, form start/submit, scroll depth.
8. **Yayın:** preview → prod; rollback.

## Kanıt

- Wireframe/copy taslağı.
- Screenshot (mobil/masaüstü).
- CWV raporu.
- Event şeması.
- Preview URL.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Mesaj | 5 saniyede anlaşılır |
| CTA | Tek ana eylem |
| A11y | Kontrast/focus/klavye |
| Performans | CWV budget |
| Analytics | CTA/form event |
| Yayın | Preview + rollback |

## Anti-pattern'ler

- Her şeyi CTA yapmak.
- Stok görsel + jenerik metin.
- Formda gereksiz alan.
- CWV'yi görmezden gelmek.
- Event'siz yayın.

## Handoff

Designer'a: state/copy.
Developer'a: component + event.
Growth/run'a: funnel hipotezi.
