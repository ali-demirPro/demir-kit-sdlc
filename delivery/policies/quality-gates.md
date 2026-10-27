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

## Gate tanımları

### behavior

- `ecosystem.yaml` surface komutu, `{checkpoint}` yerine CP id.
- `tests_plan` case'leri test edilir; exit `0` zorunlu.
- Test önce yazılır (red), sonra uygulama (green).

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

### human

- `high` leaf: [human-qa-done.md](human-qa-done.md) leaf bölümü; evidence'da
  `reviews.human: approved`.
- `critical`: iki insan (biri store/deploy sahibi); evidence'da `reviews.human`
  ve `reviews.human_second` birlikte `approved`.
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
./delivery/scripts/doctor.sh --issue 12 --checkpoint CP-1   # behavior + seal
./delivery/scripts/doctor.sh --issue 12                     # seal + evidence
./delivery/scripts/guard.sh --issue 12                      # G1 + risk escalation
```
