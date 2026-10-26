# Health check

`agent-approved` sonrası, ilk CP'den önce. `ready: false` ise CP-1 başlamaz.

## Kontroller

1. `ecosystem.yaml` var; her `surfaces.*.path` dizini mevcut.
2. Surface'ın `gates.behavior` komutu çalıştırılabilir (`{checkpoint}` → `CP-HEALTH`).
3. UI CP varsa `gates.ui: true` ve `ui_compare` tanımlı.
4. `gh auth status` OK (GitHub tracker).
5. Orca kullanılacaksa `orca status --json` OK.
6. Profile `architecture_baseline_required` ise `architecture-baseline-done` var veya waive kayıtlı.
7. Architect review açıksa (risk `high`/`critical` veya CP `gates.architect`) `docs/architecture/boundaries.md` mevcut.
8. Greenfield ise `discovery-approved` + onaylı brief (veya `decisions` içinde waive).
9. `factory.pilot_mode` ise MVO kuralları uygulanmış.
10. Feasibility blocker varsa `blocked` + karar kaydı (`decisions` text).
11. Profile `commercial_baseline_required` ise `commercial-baseline-done` + positioning/gtm dosyaları.
12. Ücretli yüzey varsa `monetization-brief.md` mevcut.

## Çıktı

```yaml
ready: true
blockers: []
warnings: []
```

`ready: false` → `blocked` etiketi + [escalation.md](../policies/escalation.md)
formatında tek soru. Waive yalnız `decisions` kaydıyla olur.

## v2 notu

Self-host (kit) reposunda 6–8 ve 10–12 `not_applicable` sayılır; 1–5 ve 9
zorunludur. `kit-internal` profili bunu `architecture_baseline_required: false`
ve `commercial_baseline_required: false` ile ifade eder.
