# Health check

`agent-approved` sonrası, ilk CP'den önce. `ready: false` ise CP-1 başlamaz.

## Kontroller

1. `ecosystem.yaml` var; her `surfaces.*.path` dizini mevcut.
2. Surface'ın `gates.behavior` komutu çalıştırılabilir (`{checkpoint}` → `CP-HEALTH`).
3. UI CP varsa `gates.ui: true`; `ui_compare` ya tanımlı ya da bilinçli `none`
   (o zaman snapshot uyarıdır, hata değil).
4. UI yüzeyinde `gates.snapshot` tanımlı; `doctor` bunu `ecosystem` kontrolünde
   arar. `ui_compare` gerçek bir mod ise snapshot zorunludur; `none` ise uyarı.
   Geçiş için tarihli `gates.ui_waiver` kullanılabilir (süresi dolunca hata).
5. Native yüzeyde `gates.selftest` tanımlıysa çalıştırılabilir; tanımlı
   değilse `behavior` komutu self-test'i kapsamak zorunda.
6. `gh auth status` OK (GitHub tracker).
7. Orca kullanılacaksa `orca status --json` OK ve epic worktree hazır:
   `epic_worktree.py ensure --epic <E>` (worktree + run). Sürüm karşılaştırması
   yapılmaz; `orca_capabilities.py --check <komut>` ile kullanılan özellikler
   doğrulanır. Eksik özellik degrade kaydı ister.
8. `orca worktree ps --json` ve `orca host list --json` çalışıyor.
9. UI web ise `orca tab profile list --json`; native/mobil ise
   `orca computer permissions --json` ve `orca emulator list --json`.
10. Profile `architecture_baseline_required` ise `architecture-baseline-done` var veya waive kayıtlı.
11. Architect review açıksa (risk `high`/`critical` veya CP `gates.architect`) `docs/architecture/boundaries.md` mevcut.
12. Greenfield ise `discovery-approved` + onaylı brief (veya `decisions` içinde waive).
13. `factory.pilot_mode` ise MVO kuralları uygulanmış.
14. Feasibility blocker varsa `blocked` + karar kaydı (`decisions` text).
15. Profile `commercial_baseline_required` ise `commercial-baseline-done` + positioning/gtm dosyaları.
16. Ücretli yüzey varsa `monetization-brief.md` mevcut.

## Araç tablosu

`health_check.py` bu tabloyu tek kaynaktan okur; satır sayısı 16'dan saparsa
veya bilinmeyen araç adı geçerse hata verir. `required: true` satırın aracı
PATH'te yoksa çıktı `ready: false` olur ve tek escalation sorusu yazılır;
`required: false` satır `not_run` olarak raporlanır, pass sayılmaz. `pass`
yalnız aracın PATH'te olduğunu söyler; kontrolün kendisi ayrıca koşulur.

| # | Kontrol | Araç | required |
|---|---------|------|----------|
| 1 | ecosystem.yaml ve yüzey yolları | python3 | true |
| 2 | behavior komutu çalıştırılabilir | bash | true |
| 3 | UI CP gates.ui ve ui_compare | python3 | true |
| 4 | UI snapshot tanımı | python3 | true |
| 5 | native selftest | python3 | true |
| 6 | gh auth status | gh | true |
| 7 | orca status ve epic worktree | orca | true |
| 8 | orca worktree ps ve host list | orca | false |
| 9 | orca tab, computer ve emulator | orca | false |
| 10 | architecture baseline kaydı | gh | false |
| 11 | architecture boundaries.md | python3 | true |
| 12 | discovery-approved ve brief | gh | false |
| 13 | pilot_mode MVO kuralları | python3 | false |
| 14 | feasibility blocker kararı | python3 | false |
| 15 | commercial baseline ve positioning | gh | false |
| 16 | monetization-brief.md | python3 | false |

## Çıktı

```yaml
ready: true
blockers: []
warnings: []
```

`ready: false` → `blocked` etiketi + [escalation.md](../policies/escalation.md)
formatında tek soru. Waive yalnız `decisions` kaydıyla olur.

## v2 notu

Self-host (kit) reposunda 8–10 ve 12–14 `not_applicable` sayılır; 1–7 ve 11
zorunludur. `kit-internal` profili bunu `architecture_baseline_required: false`
ve `commercial_baseline_required: false` ile ifade eder.
