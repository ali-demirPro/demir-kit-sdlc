# Fabrika profilleri

Her dosya bir **factory.profile** adıdır (`apple-native-excellence` → `apple-native-excellence.yaml`).

`factory-routing` skill sohbet sonunda profil seçer; `work-package` mühürde issue YAML `factory` bloğuna yazır.

Orca coordinator profil + pack checklist’lerini okur → ek gate’ler ve `tests_plan` maddeleri.

Greenfield sırası: **`kit-envision`** → **`kit-init`** → triage → routing → baselines (veya `factory.waived_baselines` per brief Handoff) → `greenfield_product`.

Tek referans: `references/product-lifecycle.md`.

Profillerde `optional_capabilities` / `default_skips` — `capability-activation.md`.

Örnek profiller:

| Profil | Kullanım |
|--------|----------|
| `apple-native-excellence` | SwiftUI iOS, platform_excellence |
| `flutter-platform` | Flutter iOS+Android |
| `web-product` | Full stack web + marketing |
| `game-flutter` | Oyun client + liveops pack |
| `store-release` | ASC / Play odaklı, minimal kod |

CLASH veya herhangi bir ürün adı burada **yok** — sadece profil isimleri.
