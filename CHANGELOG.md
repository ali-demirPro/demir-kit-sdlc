# Changelog

## 2.2.0 — 2026-10-26

- **Contract** — tek durum makinesi (`delivery/CONTRACT.md`): T1–T9 geçişleri,
  risk tabanlı insan kapıları (C), DoD ve I1–I10 değişmezleri.
- **Schemas** — leaf/epic/evidence/closure v2 (`demir_kit_version: "2"`);
  AC ↔ tests_plan kapsaması ve evidence `pass` koşulu şemayla zorlanır.
- **Protocol** — execution (kuyruk, claim, heartbeat, resume, bütçe), seal,
  health-check, evidence.
- **Policies** — quality-gates ve escalation eklendi; path-routing registry v3
  ile hizalandı; approval/human-qa risk C'ye göre yenilendi.
- **Scripts** — `doctor` (link, registry, etiket, şema, sürüm), `guard`
  (G1 + risk glob), `next-leaf` (bağımlılık kuyruğu), `install` (yerel kaynak,
  `--legacy` geçiş yolu).
- **Self-host** — `ecosystem.yaml`, `kit.config.yaml`, `kit-internal` profili;
  Epic 0 tamamlandı: 5 leaf `leaf-done`, closure `pass`.
- **Skills** — 8 runtime skill `skills/` altına taşındı; `install.sh` yerel ağaçtan
  kurulum yapar, sessiz GitHub fallback yok.
- **CI** — `.github/workflows/doctor.yml` strict modda (push + pull_request).
- **Metrics** — `delivery/metrics/README.md`; closure altı metriği zorunlu,
  aylık retro döngüsü tanımlı.
- `old/` arşiv; `delivery/` runtime'ı arşive referans vermez.

## 2.1.1 — 2026-10-13

- **delivery/agents/analist/** — full product analyst ROLE, how (intake / pre-seal / closure), SKILL templates.
