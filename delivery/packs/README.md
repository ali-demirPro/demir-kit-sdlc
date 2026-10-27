# Platform pack'ler

Pack = profilde listelenen kalite modülü. Platform gate bu checklist'leri
kanıt olarak okur; profil `platform_packs` listesi hangi modüllerin açık
olduğunu belirler.

| Pack | Gate id | Ne doğrular |
|------|---------|-------------|
| `apple-hig` | platform.hig | Human Interface Guidelines (UI reviewer checklist) |
| `apple-a11y` | platform.a11y | VoiceOver, Dynamic Type, contrast, Reduce Motion |
| `apple-privacy` | platform.privacy | Privacy manifest, ATT, required reason APIs |
| `apple-asc` | platform.store | App Store Connect metadata, screenshots spec |
| `google-play` | platform.play | Play Console listing, data safety |
| `web-ux` | platform.web_ux | WCAG smoke, Core Web Vitals (opsiyonel script) |
| `flutter-multi` | platform.flutter_parity | iOS/Android parity checklist |
| `game-liveops` | platform.liveops | IAP, age gate, ATT where applicable |
| `launch-readiness` | platform.launch | Commercial + listing alignment before human store submit |

Çalıştırma: `platform-gate` skill + `delivery/packs/<pack>/checklist.md`

Profil listesi açık modülleri belirler; script varsa `ecosystem.yaml`
`surfaces.*.gates` altında tanımlanır.
