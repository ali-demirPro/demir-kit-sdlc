# Health check

`agent-approved` sonrası, ilk CP'den önce. `ready: false` ise CP-1 başlamaz.

## Kontroller

1. `ecosystem.yaml` var; her `surfaces.*.path` dizini mevcut.
2. Surface'ın `gates.behavior` komutu çalıştırılabilir (`{checkpoint}` → `CP-HEALTH`).
3. UI CP varsa `gates.ui: true` ve `ui_compare` tanımlı.
4. `gh auth status` OK (GitHub tracker).
5. Orca kullanılacaksa `orca status --json` OK ve epic worktree hazır:
   `epic_worktree.py ensure --epic <E>` (worktree + run). Sürüm karşılaştırması
   yapılmaz; `orca_capabilities.py --check <komut>` ile kullanılan özellikler
   doğrulanır. Eksik özellik degrade kaydı ister.
6. `orca worktree ps --json` ve `orca host list --json` çalışıyor.
7. UI web ise `orca tab profile list --json`; native/mobil ise
   `orca computer permissions --json` ve `orca emulator list --json`.
8. Profile `architecture_baseline_required` ise `architecture-baseline-done` var veya waive kayıtlı.
9. Architect review açıksa (risk `high`/`critical` veya CP `gates.architect`) `docs/architecture/boundaries.md` mevcut.
10. Greenfield ise `discovery-approved` + onaylı brief (veya `decisions` içinde waive).
11. `factory.pilot_mode` ise MVO kuralları uygulanmış.
12. Feasibility blocker varsa `blocked` + karar kaydı (`decisions` text).
13. Profile `commercial_baseline_required` ise `commercial-baseline-done` + positioning/gtm dosyaları.
14. Ücretli yüzey varsa `monetization-brief.md` mevcut.

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
