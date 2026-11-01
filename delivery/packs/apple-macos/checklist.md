# apple-macos pack

macOS yüzeyi için platform gate checklist'i. UI gate'ten sonra çalışır.
Blocker = gate fail. Kural kaynakları canlı HIG ve Apple dağıtım belgeleridir;
sürüm koşulları yazılıdır.

1. **Menü çubuğu tamlığı** — her komut bir menüde; File/Edit/View/Window/Help
   dolu; Window menüsü açık pencereleri listeler. (HIG — The menu bar)
2. **Kısayol hijyeni** — her komuta kısayol, çakışma yok, ⌘, Settings'i açar,
   ⌘W pencereyi kapatır, ⌘Q uygulamayı kapatır. (HIG — Keyboards)
3. **Toolbar** — öğe önceliği tanımlı, overflow davranışı belli,
   özelleştirme gerekiyorsa desteklenir. (HIG — Toolbars)
4. **Sidebar** — kaynak listesi olarak çalışır, genişliği ayarlanabilir,
   seçim kalıcı. (HIG — Sidebars)
5. **Pencere davranışı** — minimum boyut, restore, çoklu ekran ve full screen
   tanımlı; içerik kırpılmıyor. (HIG — Windows)
6. **Kontrol seçimi** — native kontrol; dokunma hedefi kuralı (44×44 pt)
   uygulanmaz, macOS ölçüsü kullanılır. (HIG — Controls)
7. **Tipografi** — apple-hig'in tipografi maddesi geçerli; macOS farkı: 13 pt
   gövde ve 4 pt ızgara, büyük ekranda okunabilirlik. (HIG — Typography)
8. **Erişilebilirlik** — VoiceOver sırası, Full Keyboard Access, Increase
   Contrast, Reduce Motion/Transparency. (HIG — Accessibility)
9. **Liquid Glass** — apple-hig'in functional-layer kuralı geçerli; macOS farkı
   sürüm koşulu: yalnız macOS 26+ hedefinde. (HIG — Materials)
10. **Sandbox ve entitlement** — minimum yetki; dosya erişimi security-scoped
    bookmark ile; ağ yalnız istemci. (Apple — App Sandbox)
11. **İmza ve notarization** — hardened runtime, timestamp, staple; DMG/zip
    imzalı. (Apple — Notarizing macOS software)
12. **Güncelleme kanalı** — tek kanal seçili; iki kanal birlikteyse ADR'de
    gerekçesi var. (`delivery/policies/quality-gates.md` — human)
13. **Veri ve migration** — store konumu tek yerde, migration planı ve yedek
    tanımlı; şema değişiminde varsayılan değer. (HIG — Entering data)
14. **Gizlilik ve log** — kullanıcı verisi loglanmıyor; hata mesajı veri
    sızdırmıyor. (HIG — Privacy)

Madde 10–12 HIG değil Apple dağıtım belgelerine dayanır (App Sandbox,
Notarizing macOS software); diğer maddeler HIG sayfalarına bağlıdır.

Output: JSON `{ "pass": bool, "findings": [...] }` per `ui-gate` format;
bulgular `HIG-*` veya `MAC-*` (severity `critical|high|medium`, kaynak zorunlu).
