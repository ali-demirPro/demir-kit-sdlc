# Quality gates

Risk tabanlı gate matrisi. Sözleşme: [CONTRACT.md](../CONTRACT.md) · Risk verisi:
[registry.yaml](../registry.yaml) `risk`.

## Matris

| Risk | behavior | architect | commercial | ui | adversarial | platform | insan |
|------|-----------|-----------|------------|----|-------------|----------|-------|
| `low` | zorunlu | — | — | `gates.ui` ise | 1 reviewer | — | — |
| `medium` | zorunlu | `gates.architect` ise | `gates.commercial` ise | `gates.ui` ise | 1 reviewer | — | bütçe aşılırsa |
| `high` | zorunlu | zorunlu | `gates.commercial` ise | `gates.ui` ise | 2 reviewer | profil varsa | `reviews.human` |
| `critical` | zorunlu | zorunlu | zorunlu | `gates.ui` ise | 2 reviewer | profil varsa | `reviews.human` + `human_second` |

`low` / `medium` otomatik kapanır; insan spot-check yapar. Epic kabulü her zaman insandır.

`entry.kind: refactor` leaf'lerinde `architect` gate'i riskten bağımsız olarak
her checkpoint'te zorunludur; `verification.refactor` olmadan `leaf-done` geçmez.

## Rigor

Tören ağırlığı `kit.config.yaml` → `process.rigor` ile bir kez seçilir
(`minimal` | `standard` | `full`; alan yoksa `standard`). Yayma tablosu:
[rigor.yaml](../rigor.yaml). Rigor yalnız doküman derinliğini, kanıt kümesini,
leaf/CP granülerliğini, aktif roster'ı ve ek test kanıtını değiştirir; bu
matristeki risk tabanı ve insan kapısı değişmez. Gating reviewer sayısı
risk-only kalır (`low`/`medium` 1, `high`/`critical` 2). `modes.review_mode`
saklanır, sayıyı ve `gate_level`'ı değiştirmez.

## Yüzey kanıtı

Bir ürünün `ecosystem.yaml` yüzeyi kendi kanıt seviyesini bildirir:

| `ui` | `ui_compare` | `snapshot` | Sonuç |
|------|--------------|------------|-------|
| `true` | yok / `none` | yok | **uyarı** — UI gate henüz kanıt üretmiyor |
| `true` | gerçek mod | var | geçer |
| `true` | gerçek mod | yok | **hata** |
| `true` | gerçek mod | yok + geçerli `ui_waiver` | **uyarı** (bitiş tarihi yazılır) |
| `true` | gerçek mod | yok + süresi dolmuş/bozuk muafiyet | **hata** |

Muafiyet ürünün kendi `ecosystem.yaml` dosyasında yaşar; kit'e yama yapılmaz.
`reason` boş olmayan string, `issue` pozitif tam sayı, `until` en fazla 180 gün
ileri olmalı; snapshot eklendikten sonra kalan muafiyet "artık gereksiz" uyarısı
verir, süresi dolmuş muafiyet her durumda hatadır.

```yaml
gates:
  ui: true
  ui_compare: screenshot
  ui_waiver: { reason: "snapshot araci hazirlaniyor", until: "2026-12-15", issue: 12 }
```

## CI kanıtı

- `critical`: CI `success` zorunlu; `skipped` kabul edilmez.
- `high`: CI `success` veya yerel kapı (`verification.local_gate` +
  `exit_code: 0`) kabul edilir; gerekçe `ci.reason` alanında yazılır.
- `low` / `medium`: yerel gate yeterli; CI varsa kaydedilir.

## Gate tanımları

### behavior

- `ecosystem.yaml` surface komutu (`gate.sh`), `{checkpoint}` yerine CP id.
- `tests_plan` case'leri test edilir; exit `0` zorunlu.
- Test önce yazılır (red), sonra uygulama (green).
- Kapı salt-okurdur: izlenen veya yeni dosya değişirse kapı düşer. Düzeltici
  komutlar yüzeyin `gates.fix` alanında durur ve yalnız `--fix` ile koşar.

### architect

- Yalnız `gates.architect` veya risk `high`/`critical`.
- `docs/architecture/boundaries.md` ve `cost-and-tiers.md` ile diff karşılaştırılır.
- Verdict: `approved` | `revise_required` (`AR-*`). Maks 3 tur.
- Architect kod yazmaz; `revise_required` uygulayıcıya döner.

### commercial

- Marketing/store/paid yüzey varsa veya `gates.commercial`.
- `positioning.md`, `gtm-lite.md`, `monetization-brief.md` ile uyum.
- Verdict: `approved` | `revise_required` (`CR-*`). Maks 3 tur.

### ui

- `gates.ui` ise iki bağımsız reviewer: `visual` + `interaction`.
- Referans/prototype + screenshot; repo agent kuralları **okunmaz**.
- `comparison_valid: false` → pass yok; aynı state yeniden çekilir (maks 2).
- Geçiş: `reviews.ui_visual: pass` + `reviews.ui_interaction: pass` +
  `reviews.comparison_valid: true` (doctor üçünü birlikte arar).

### adversarial

- `low`/`medium`: 1 reviewer; `high`/`critical`: 2 bağımsız reviewer.
- Reviewer'lar birbirinin çıktısını görmez; lint + diff + docs okur.
- Bulgular `ADV-*`; fixer sonrası yeniden review (maks 5 tur).
- UI'a dokunan fix → ui gate yeniden.

### platform

- `factory.profile` `platform_packs` / `extra_gates` varsa.
- Pack checklist (`delivery/packs/`) madde madde kanıtlanır.
- Apple pack'lerinde tam denetim prosedürü: `skills/hig-audit/SKILL.md`
  (`HIG-*` bulguları, canlı HIG referansı).

### human

- `high` leaf: [human-qa-done.md](human-qa-done.md) leaf bölümü; evidence'da
  `reviews.human: approved`. İnsan kapısı istendiğinde `update.py --human-gate`
  (veya `--approval yes --ask "..."`) kullanılır; aksi halde "Onay: gerekmiyor"
  yazılamaz.
- `critical`: iki insan (biri store/deploy sahibi); evidence'da `reviews.human`
  ve `reviews.human_second` birlikte `approved`.
- `package_version: 4` leaf'te `gates.human: true` olan CP, risk düşük olsa da
  `leaf-done` anında `reviews.human: approved` ister. `manual` test türü bu
  kapıyı seal anında zorunlu kılar.
- Aktif bir capability `gates` listesinde `human` bildiriyorsa (ör.
  `distribution.direct`), seal'de en az bir CP `gates.human: true` olmalı;
  `doctor` bunu denetler. Dağıtım gibi geri dönüşü zor işler kendiliğinden
  kapanmaz.
- İnsan onayı yoksa `doctor --issue` `leaf-done`'ı reddeder; etiket elle
  kaldırılamaz.
- Epic: closure **pass** sonrası kabul.
- Geri dönülemez işlem (store submit, prod deploy, fiyat, yıkıcı migration) her zaman insan.

## Risk otomatik yükseltme

`registry.yaml` `risk.auto_escalate.high` glob'larından biri diff'e değerse seviye
`high` olur; `critical` glob'u ise `critical`. Agent düşüremez; seal'de gerekçe yazar.
`scripts/guard.sh` bu kuralı **registry'den okuyarak** diff üzerinde uygular;
capability `risk_floor` seal riskinin altına inemez (`doctor`).

## Bağımsızlık

| Kural | Neden |
|-------|-------|
| Uygulayan onaylayamaz | self-approval kalite kapısını etkisizleştirir |
| Reviewer temiz context | önceki karar yanlılığı |
| Reviewer'lar izole | ikinci görüş gerçekten ikinci olsun |
| UI reviewer repo kuralı okumaz | "bizde böyle" savunması |

## Definition of done

- **CP:** behavior exit 0 + risk gate'leri + evidence `status: pass`.
- **Leaf:** tüm CP'ler + AC kapsaması + açık bulgu yok + risk insan gate'i.
- **Epic:** closure `pass` + insan kabul + metrikler.

## Komutlar

```bash
./delivery/scripts/gate.sh --issue 12 --checkpoint CP-1        # doctor + değişen dosyanın test modülleri
./delivery/scripts/gate.sh --issue 12 --checkpoint CP-1 --full # tam unittest paketi (closure/CI)
./delivery/scripts/gate.sh --issue 12 --checkpoint CP-1 --fast # yalnız doctor (CP)
./delivery/scripts/doctor.sh --issue 12                     # seal + evidence
./delivery/scripts/guard.sh --issue 12                      # G1 + risk escalation
```

Varsayılan seviye **selected**: değişen test dosyası kendini, değişen betik onu
adlandıran test modüllerini, değişen şema/config onu anan testleri seçer. Tam
paket yalnız `--full` ile koşar. `leaf-done` kapısını `transition` Orca
terminalinde koşturur ve sonucu dosyadan okur.
