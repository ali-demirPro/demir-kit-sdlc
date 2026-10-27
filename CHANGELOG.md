# Changelog

## 2.10.0 — 2026-10-27

- **Developer variants** — web, iOS, Android, API/CLI, domain (auth/payments/
  data/offline/i18n/analytics), quality ve delivery playbook'ları; 3 eval seti.
- **Marketing/stores** — Apple, Google ve ASO/analytics/i18n variant'ları;
  metadata, privacy, rollout ve dönüşüm kriterleri.
- **Marketing/landing** — landing ve SEO/analytics/i18n variant'ları; CWV,
  a11y, event ve canonical/hreflang kriterleri.
- **Kapsam** — 12 variant dokümanı, 5 eval seti (10+ senaryo); 195 test.

## 2.9.0 — 2026-10-27

- **Architect variants** — web, mobile, API/CLI, data/offline, security,
  operability ve release modülleri; ADR/boundary/NFR/CP DAG kriterleri.
- **DevOps variants** — web, API, mobile (Apple/Google) ve observability;
  CI/CD, migration, signing, rollout, SLO ve rollback kriterleri.
- **Security variants** — application, mobile, payments/auth, data/privacy ve
  threat model; authz, secret, tedarik zinciri ve `SEC-*` beklentileri.
- **Eval** — architect/devops/security için 6 dosya, 10+ senaryo; `variants.py`
  min_level ↔ rol matrisi çapraz kontrolü.

## 2.8.0 — 2026-10-27

- **Agent variants** — `designer` ve `tester` için `agent.yaml` capability →
  variant/eval/min_level eşlemesi; web, iOS ve Android davranış modülleri.
- **Kriterler** — Her variant platforma özgü yöntem, state/kanıt matrisi, gate
  rubriği, anti-pattern ve handoff taşır; her eval seti 8+ senaryo içerir.
- **Şema/doctor** — `agent.schema.json`; doctor capability, rol, dosya ve seviye
  referanslarını doğrular. `variants.py --role` aracı eklendi.
- **Pilot sınırı** — Variant kapsamı web/iOS/Android; diğer capability'ler
  sonraki leaf'lerde.

## 2.7.0 — 2026-10-27

- **Capability Matrix** — `delivery/capabilities/` eklendi: platform/domain/
  distribution/quality taksonomisi, `aware → practitioner → expert → authority`
  seviye doktrini, rol-capability matrisi ve risk eşleşmesi.
- **Roller** — `security`, `data`, `release` rolleri temel contract'larıyla
  eklendi; `role_order_default` güncellendi. Variant içerikleri sonraki leaf'lerde.
- **Şemalar** — `capability.schema.json` ve `role-matrix.schema.json`; doctor
  rol/pack/seviye referans bütünlüğünü doğrular.
- **Araç** — `capabilities.py --list/--matrix/--role/--capability/--validate`.

## 2.6.0 — 2026-10-26

- **Issue doctor** — `.github/workflows/issue-doctor.yml` issue açıldığında,
  düzenlendiğinde veya state etiketi değiştiğinde `doctor.sh --issue N` çalıştırır;
  `scope-confirmed`, `agent-approved`, `leaf-done`, `epic-done` durumlarını denetler.
- **PR akışı** — `.github/pull_request_template.md` ve `delivery/runbooks/pr-flow.md`
  eklendi: zorunlu kontroller, merge commit kuralı, branch protection insan adımı.
- **Doctor** — issue workflow, PR şablonu ve PR runbook'u zorunlu dosyalara eklendi;
  workflow/şablon/runbook statik testlerle doğrulanır.

## 2.5.0 — 2026-10-26

- **Transition CLI** — `transition.py`/`transition.sh` T1–T9 geçişlerini tek
  yazıcıya alır: hedef state'i doğrular, doctor preflight'ını hedef etiket
  varsayımıyla çalıştırır, ancak sonra label delta'sını uygular. `--dry-run`
  yazmaz; aynı hedefe geçiş no-op'tur.
- **Doctor** — `--assume-label` / `--drop-label` eklendi; geçiş öncesi hedef
  etiketle doğrulama yapılabilir.
- **Claim** — `next-leaf --claim --issue N` belirli bir leaf'i kiralar;
  `executing` geçişi buna delege edilir.
- **Epic kabulü** — `epic-done` closure `pass` + `--accept` insan adı ister;
  kabul `demir-kit-accept` yorumuyla kaydedilir.

## 2.4.0 — 2026-10-26

- **Evidence v3** — `verification` bloğu: commit SHA, binary diff hash, CI sonucu
  ve reviewer kimliği/model/prompt hash. `package_version: 2` leaf'lerde zorunlu;
  eski `package_version: 1` kayıtları geçerli.
- **Doctor** — commit'in varlığını, diff hash eşleşmesini, CI run'ın aynı commit'te
  `success` olduğunu ve reviewer ID'lerinin benzersiz/uygulayıcıdan farklı olduğunu
  doğrular. `high`/`critical` için CI `skipped` reddedilir.
- **Araç** — `delivery/scripts/evidence.py` verification üretir; `evidence.md`
  v3 şablonu ve kuralları güncellendi.

## 2.3.0 — 2026-10-26

- **Gate integrity** — `doctor` artık `epic-done` için closure `status: pass` ve
  `ready_for_human_qa: true` arar; `high`/`critical` leaf'te `reviews.human`
  (critical'da ayrıca `human_second`) olmadan `leaf-done` geçmez.
- **Commercial + UI** — `gates.commercial` veya risk `critical` için
  `reviews.commercial: approved`; `gates.ui` için `ui_visual`, `ui_interaction`
  ve `comparison_valid: true` birlikte zorunlu.
- **Doctor** — Issue yorumları sayfalanır; `leaf-done` + `executing`/`blocked` ve
  `epic-done` + `epic-reconcile` çelişkileri hata verir; stale `human-qa` etiketi
  kapanışı bloklamaz.
- **Evidence** — `reviews.human`, `human_second`, `ui_visual`, `ui_interaction`
  alanları eklendi; protokol ve kalite kapıları güncellendi.

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
- `archive/v1.7/` arşiv; `delivery/` runtime'ı arşive referans vermez.

## 2.1.1 — 2026-10-13

- **delivery/agents/analist/** — full product analyst ROLE, how (intake / pre-seal / closure), SKILL templates.
