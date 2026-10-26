# Platform pack'ler

Pack = zorunlu kalite modülü. `quality_tier: platform_excellence` profilde listelenen **tüm** pack'ler zorunludur; `standard` profilde alt küme.

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

Çalıştırma: `platform-gate` skill + `references/packs/<pack>/checklist.md`

Ürün repo'sunda gate komutları: `ecosystem.yaml` → `surfaces.*.gates.platform_<pack>` (opsiyonel script path).
