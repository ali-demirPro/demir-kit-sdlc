# Architecture boundaries — demir-kit-sdlc

Bu dosya bu reponun (demir-kit-sdlc, self-host) **modül haritasını** ve **değişmez
sınırlarını** tarif eder. Architect kapısı
(`delivery/policies/quality-gates.md` → `gates.architect`) bir diff'i bu dosyayla
kıyaslar: diff bir modüle dokunuyorsa, o modülün "içeri girebilir / giremez"
kuralları ve denetim yolu bu dosyada aranır. Mimari kararlar (ADR) ve maliyet
politikası bu dosyanın kapsamı dışındadır.

## Purpose

Architect review ve D-1 (#373) kıyası bu reponun sınırlarını tek yerden okusun
diye yazıldı. Kapı sorusu basittir: "Bu değişiklik hangi modüle ait, modülün
değişmezleri neler, denetimi kim yapar?" Bu dosya o sorunun kıyas temelidir;
sözleşmenin kendisi değildir. Sözleşme metni `delivery/CONTRACT.md`'dedir, bu
dosya ona işaret eder, asla onun yerine geçmez. Değişirse: modül ya da sınır
değiştiyse doktor/testlerle birlikte güncellenir, yoksa bu dosya bayatlar ve
architect kapısı yanlış kıyas yapar.

## Module map

| Modül | Sorumluluk | Durum |
|-------|------------|-------|
| `delivery/` | Çalışma zamanının tamamı: sözleşme, politika, şema, script, test | Aktif runtime |
| `delivery/CONTRACT.md` | Tek durum makinesi; T1–T9 geçişleri, risk modeli, DoD, değişmezler | Sözleşme (v2.65) |
| `delivery/registry.yaml` | Yollar, agent envanteri, etiketler, risk glob'ları — tek kaynak | Registry |
| `delivery/schemas/` | `demir_kit_version: "2"` leaf / epic / evidence / closure şemaları | Şema |
| `delivery/policies/` | Kapılar (`quality-gates.md`), onay, eskalasyon, context bütçesi | Politika |
| `delivery/protocol/` | Sözleşme protokolleri (execution, seal, health-check, evidence, status, orca…) | Protokol |
| `delivery/agents/` | Rol tanımları ve varyantları (`<rol>/agent.yaml`) | Roller |
| `delivery/runbooks/` | Operasyonel akışlar (epic intake/closure, update, adaptation) | Runbook |
| `delivery/scripts/` | Uygulama: `doctor.sh`, `guard.sh`, `gate.sh`, `transition.sh`, `install.sh` … | Script |
| `delivery/tests/` | Python unittest paketi | Test |
| `delivery/capabilities/`, `delivery/profiles/`, `delivery/packs/` | Capability registry + rol matrisi, profil besteleri, ürün paketleri | Runtime veri |
| `delivery/templates/`, `delivery/automations/`, `delivery/plans/` | Etiket/CI şablonları, zamanlanmış işler, plan dosyaları | Runtime veri |
| `delivery/context/`, `delivery/metrics/`, `delivery/orchestrator/` | Context indeksi, closure metrik tanımları, orchestrator rolü | Destek |
| `skills/` | v2 çalışma zamanı skill'leri (SKILL.md); `registry.yaml` `skills.runtime` listesi | Kaynak |
| `discovery/` | Aşamalı sonraki faz agent'ı (`growth/plan`); kurulu ve vendored değil | Aşamalı |
| `archive/v1.7/` | Legacy 1.x referansı; yalnız taşıma ve okuma | Salt okunur |
| `.agents/skills/` | `install.sh` çıktısı (proje seviyesi skill kopyası) | Kurulum çıktısı |
| `docs/` | Yeni mimari kayıtlar (bu dosya burada) | Kayıt |
| `plugins/` | Orca plugin'i (`plugins/orca`); gate davranışında ayrı süit koşar | Runtime |
| `ecosystem.yaml`, `kit.config.yaml` | Self-host wiring: bu repo hem kit hem ürün | Wiring |

Not: görev/örnek metinlerinde `protocols/` olarak geçen dizin bu repoda
`delivery/protocol/` (tekil) olarak yaşar; doğru yol odur.

## Boundaries (immutable)

Her sınır için: ne içeri girebilir, ne giremez, denetimi nasıl yapılır.

### B1 — Contract (`delivery/CONTRACT.md`)

- **Girebilir:** States, T1–T9 geçiş tablosu, risk model, DoD ve invariants'ın
  metinsel karşılığı; `VERSION` + `CHANGELOG.md` + README başlığı ile birlikte değişir.
- **Giremez:** Registry verisi (yol/glob/etiket), şema gövdeleri, script mantığı;
  bunlar sözleşmeye değil kendi dosyalarına aittir. Sözleşme metni tek taraflı
  "düzeltilmez"; contract değişikliği = VERSION + CHANGELOG + `doctor.sh --strict` yeşil.
- **Denetim:** `./delivery/scripts/doctor.sh` (version/contract kontrolü) +
  `python3 -m unittest discover -s delivery/tests`.

### B2 — Registry (`delivery/registry.yaml`)

- **Girebilir:** Yol/path routing, agent envanteri, etiket adları, risk seviyeleri
  ve `risk.exclude` glob'ları; `skills.runtime` listesi.
- **Giremez:** Sözleşme metni, şema gövdesi, davranış mantığı; registry "tek kaynak"tır,
  ikinci bir yol/glob listesi başka dosyada yaşayamaz (prose registry ile çelişirse
  registry kazanır, prose düzeltilir).
- **Denetim:** `doctor.sh` + `delivery/tests/` (registry tutarlılık testleri).

### B3 — Schemas (`delivery/schemas/`)

- **Girebilir:** `demir_kit_version: "2"` leaf/epic/evidence/closure ve diğer
  artefakt şemaları; geriye uyumluluk yalnız açıkça tanımlı alanlarla.
- **Giremez:** Şema ile uyuşmayan evidence/seal yorumları; şema gevşetilerek
  kapı atlanamaz — `T4` evidence şeması geçerli değilse imkânsızdır.
- **Denetim:** `./delivery/scripts/doctor.sh --body <seal>` / `--issue N` +
  `python3 -m unittest discover -s delivery/tests`.

### B4 — Archive (`archive/v1.7/`)

- **Girebilir:** 1.x dosyalarının taşınması, okuma/karşılaştırma referansı;
  `--legacy` kurulumunun kaynağı (loud warning ile).
- **Giremez:** Yeni bağımlılık, yeni referans, runtime yolundan çağırma; yeni
  runtime asla arşive bağlanmaz — `install.sh --legacy` açık istisnası dışında.
- **Denetim:** `doctor.sh` (legacy kontrolü) + `delivery/tests/` + code review.

### B5 — Skills → `.agents/skills/` (tek yön)

- **Girebilir:** `skills/` altındaki `SKILL.md` kaynakları; `install.sh`
  (`npx skills add`) proje dizinine `.agents/skills/` kopyasını üretir.
- **Giremez:** Elle kopyalama, `.agents/skills/` altında elle düzenleme; kaynak
  daima `skills/`'tir, kopya çıktıdır — çakışmada `skills/` kazanır; kopya
  güncellemesi her zaman `install.sh` iledir.
- **Denetim:** `install.sh --dry-run` + `doctor.sh` (skill denetimleri) + review.

### B6 — Root çözümleme (iki ayrı fonksiyon)

- **Girebilir:** İki ayrı fonksiyon, ayrı ayrı tarif edilir — ikisi de "tek
  doğru kök" değil, bugünkü gerçek davranıştır:
  1. `delivery/scripts/guard.sh` — `PRODUCT_ROOT`: `git -C "${PWD}"
     rev-parse --show-toplevel` kullanır (yedeği `pwd`):
     **mevcut çalışma ağacının** köküdür; linked worktree'de worktree'nin
     kendisidir, ortak kök DEĞİL. `PRODUCT_ROOT` içinde `kit.config.yaml`
     varsa ROOT orasıdır, yoksa script'in KIT_ROOT'u.
  2. `delivery/scripts/cycle.py` — `git_root()` ve onu çağıran
     `project_root()`: `git rev-parse --path-format=absolute --git-common-dir`
     kullanır: ortak git dizininin ebeveyni = **ana checkout**, worktree'den
     çağrılsa da değişmez. `kit.config.yaml` varsa orası, yoksa cwd, yoksa
     kit_root (`DEMIR_KIT_CYCLE_ROOT` ile override edilebilir).
- **Giremez:** İki kök "tekmiş gibi" varsayılan durum yazımı — cycle log'u
  (`.kit/cycle.jsonl`) ana checkout'a aittir, worktree'ye yazılan durum kopyası
  bozuk sayılır; guard'ın `show-toplevel` davranışı ile cycle.py'nin
  ortak-kök davranışı birbirinin yerine geçecek şekilde "düzeltilmez".
- **Not:** Bu tarif D-1 (#373) kitlib **tek `project_root` sözleşmesi**nin kapsamına
  işaret eder; bugün scriptler arasında birden çok tanım vardır ve kitlib bunları
  tek sözleşmede birleştirir. Bu dosya o kararı vermez, çelişmez, yalnız bugünkü
  davranışı ve hedef yönü tarif eder. Detay ve migrasyon D-1'dedir.
- **Denetim:** `doctor.sh` (`check_worktree_management` — linked worktree'nin
  Orca'da kayıtlı olduğunu doğrular) + `delivery/tests/` (`test_cycle.py`,
  `test_epic_worktree.py`) + D-1 testleri.

### B7 — Kapsam taşması yok (guard + transition)

- **Girebilir:** Yalnız seal yüzeyindeki (`surfaces`) glob'ların kapsadığı dosyalar;
  epic kapsamı dışına sessiz taşma yasaktır.
- **Giremez:** Başka epic'in kapsamı, kit genelinde "gerekirse" değişiklikler;
  kapsam dışı ihtiyaç = yeni leaf/issue, sessiz genişleme değil.
- **Denetim:** `./delivery/scripts/guard.sh --issue N` (G1 capability dışı yazım
  reddi + risk eskalasyonu) + `transition.sh --issue N` (tek yazıcı geçişleri) +
  `gate.sh --issue N --checkpoint CP-x`.

### B8 — Policies (`delivery/policies/`)

- **Girebilir:** Kapı ve süreç politikaları (`quality-gates.md`, `approval.md`,
  `escalation.md`, `path-routing.md` …); `registry.yaml` `policies:` bölümü bunların
  tek referans noktasıdır.
- **Giremez:** Sözleşme metni ve değişmezler (`delivery/CONTRACT.md`'ye aittir),
  şema gövdesi, script mantığı; politika "registry risk glob'larını genişletir"
  diye yazılamaz — çelişirse registry kazanır.
- **Denetim:** `./delivery/scripts/doctor.sh` (REQUIRED_FILES + link kontrolü +
  `check_registry` — `path-routing.md` tablosu registry `paths` ile uyuşmuyorsa
  error) + `python3 -m unittest discover -s delivery/tests` (örn. `test_doctor.py`
  policy testleri).

### B9 — Protocol (`delivery/protocol/`)

- **Girebilir:** Sözleşmenin operasyonel karşılığı: execution, seal, health-check,
  evidence, orca protokolleri; sözleşmenin "nasıl koşar"ını yazar.
- **Giremez:** Durum makinesi ve geçiş tanımları (yalnız `CONTRACT.md`), risk
  modeli; `registry.yaml` `protocol:` bloğunda adı geçmeyen yeni protokol
  runtime'a eklenemez.
- **Denetim:** `./delivery/scripts/doctor.sh` (REQUIRED_FILES: execution/seal/
  health-check/evidence/orca + link kontrolü) + registry `protocol:` referansları +
  `python3 -m unittest discover -s delivery/tests`.

### B10 — Agents / roller (`delivery/agents/<rol>/`)

- **Girebilir:** Rol başına `ROLE.md`, `how.md`, `communicates.md`,
  `dependencies.md`, `SKILL.md`; `agent_variants.roles` listesindekilerin geçerli
  `agent.yaml`'ı (capability registry ile uyumlu).
- **Giremez:** Registry'de tanımsız rol/dizin; eksik dosya setiyle "rol var" sayılma;
  rol tanımı sözleşmenin yerine geçmez.
- **Denetim:** `./delivery/scripts/doctor.sh` (`check_registry` — agent dizinleri +
  AGENT_FILES; `check_agent_variants` — schema + capabilities çapraz referansı;
  `check_role_contracts` — `how.md` içinde `## Contract`) + link kontrolü +
  `python3 -m unittest discover -s delivery/tests` (`test_variants.py`,
  `test_macos_variants.py`).

### B11 — Runbooks (`delivery/runbooks/`)

- **Girebilir:** Operasyonel akışlar: epic-intake, epic-closure, pr-flow, update,
  adaptation; adımlar CONTRACT durumlarına ve script çağrılarına işaret eder.
- **Giremez:** Yeni durum/geçiş tanımı, script mantığı, sözleşme genişletmesi;
  runbook sözleşmenin "nasıl yapılır"ını anlatır, "ne yapılabilir"ini değil.
- **Denetim:** `./delivery/scripts/doctor.sh` (REQUIRED_FILES: pr-flow/adaptation/
  update + link kontrolü) + `python3 -m unittest discover -s delivery/tests`
  (`test_ci_workflow.py` — pr-flow merge commit; `test_self_update.py` — update.md
  modları; `test_refactor.py` — epic-closure).

### B12 — Discovery (`discovery/`)

- **Girebilir:** Aşamalı sonraki-faz agent kaynakları (`discovery/agents/growth/
  plan/`); kurulu runtime'a dahil edilmediği açıkça yazılı deneme alanı.
- **Giremez:** `registry.yaml` `skills.runtime`'a girme, `install.sh` kurulu
  setine (`skills/` → proje kopyası) dahil edilme, `delivery/` runtime'ı tarafından
  çağrılma/vendored edilme.
- **Denetim:** Ayrı test süiti yoktur; `doctor.sh` link kontrolü `discovery/`'i
  taramaz. Somut mekanizma: `install.sh` yalnız `registry.yaml` `skills.runtime`
  listesini kurar (discovery listede değildir); guard kit.docs yüzeyi
  `discovery/**`'i kapsar. Runtime sızıntısı architect kapısının diff kıyasında
  bu blokla yakalanır.

### B13 — Docs (`docs/`)

- **Girebilir:** Yeni mimari kayıtlar: modül sınırları (bu dosya) ve aynı türden
  karar kayıtları; architect kapısının kıyas temasıdır.
- **Giremez:** Kod/şema/script değişikliği, sözleşme metni; kapı davranışını
  değiştiren metin buraya tek taraflı yazılamaz — sözleşme değişikliği yolu
  `CONTRACT.md` + `VERSION` + `CHANGELOG.md` + `doctor.sh --strict`'tir.
- **Denetim:** `doctor.sh` link kontrolü `docs/`'u taramaz (kapsam dışı; hedef
  varlığı review'a kalır). Bu dosyanın varlık/içerik doğrulaması architect
  review'dadır; guard (G1) açısından `kit.docs` yüzeyi `docs/**`'i kapsamaz
  (kök `*.md` common-path'i yalnız kökteki dosyalara uygulanır).

### B14 — Plugins (`plugins/orca`)

- **Girebilir:** Orca plugin kaynakları (`plugins/orca/`); panel/gate entegrasyonu
  kendi çalışma zamanında koşar.
- **Giremez:** `delivery/` runtime'ına çağrı/bağımlılık; kit sözleşmesini veya kapı
  davranışını sessiz değiştirme; plugin içine kit script kopyası.
- **Denetim:** `./delivery/scripts/gate.sh` (değişen dosya `plugins/` altındaysa Orca
  plugin süitini koşar) + `python3 -m unittest discover -s delivery/tests`
  (`test_orca_plugin.py`, `test_gate.py` — `suites_for(plugins/orca)`). doctor kapsamı
  dışıdır; guard (G1) açısından `kit.docs` yüzeyi `plugins/**`'i kapsamaz.

### B15 — ecosystem.yaml / kit.config.yaml

- **Girebilir:** Self-host wiring — bu repo hem kit hem üründür:
  `ecosystem.yaml` (`products.*.surfaces.*.path` + tracker), `kit.config.yaml`
  (`kit.protocol: "2"`).
- **Giremez:** Kit'in üründe aynı dosyaları yamaması (kit kopyasını
  `vendor_sync.sh` taşır); eksik/yanlış `surfaces.path` ile "surface var" sayılma;
  `kit.protocol` ≠ `2`.
- **Denetim:** `./delivery/scripts/doctor.sh` (`check_ecosystem` — surface path
  varlığı + `kit.protocol == "2"`) + `python3 -m unittest discover -s delivery/tests`
  (`test_surface_contract.py` — `check_ecosystem`: surface path varlığı +
  `kit.protocol == "2"`, örn. `test_check_ecosystem_reports_missing_snapshot`;
  `test_model_policy.py` model politikasını test eder — `orca.inherit_session_model`
  / `role_defaults`, `kit.config`'in `protocol` alanını değil).

### B16 — Scripts (`delivery/scripts/`)

- **Girebilir:** bash + python3 (PyYAML zorunlu) uygulama kodu — sözleşmenin
  ve registry'nin **okuyucusu** CLI'ler (`doctor.sh` → `doctor.py`, `guard.sh`,
  `gate.sh`, `transition.sh`, `next-leaf.sh`, `install.sh` …); exit code
  0/≠0 ile biten deterministik davranışlar.
- **Giremez:** Sözleşme metni, şema gövdesi, registry verisi burada icat
  edilmez — katman sırası sözleşme → registry/şema → script'tir; ikinci bir
  yol/glob/etiket listesi (registry kopyası) script içinde yaşayamaz.
- **Denetim:** `./delivery/scripts/doctor.sh` (REQUIRED_FILES script seti +
  `check_links`) + `python3 -m unittest discover -s delivery/tests`
  (`test_doctor.py`, `test_guard.py`, `test_gate.py`, `test_transition.py` …)
  + `./delivery/scripts/guard.sh` G1 (bu repoda `delivery/` ve `skills/`
  uygulama yüzeyi; seal'siz çağrıda agent-approved'suz bloklar) + risk glob'u
  (`risk_filter.py`).

### B17 — Tests (`delivery/tests/`)

- **Girebilir:** Python unittest paketi; `test_*.py` adlandırması (discover
  otomatik bulur); script'leri import ya da subprocess ile çağıran testler;
  geçici fixture dizinleri.
- **Giremez:** Production iş mantığı; script'in kopyası burada yaşamaz —
  test script'i import eder, kod klonlamaz; registry/şema verisi fixture
  içine gömülü ikinci kaynak olarak kopyalanmaz, testler repodaki gerçek
  dosyaları okur.
- **Denetim:** `python3 -m unittest discover -s delivery/tests` (CI'da
  `doctor.sh --strict` kapısıyla birlikte koşulur); registry `risk.exclude`
  içindeki `delivery/tests/**` glob'u test değişikliklerini risk
  eskalasyonuna sokmaz (seal glob'u ise `delivery/**` ile kapsar —
  bkz. denetim tablosu).

### B18 — Capabilities / profiles / packs

- **Girebilir:** Capability registry — `surfaces` + `paths` + `common_paths`
  (write-surface glob'larının tek tanımı; guard bunları kullanır), `role-matrix.yaml`,
  `levels.md`; profiller — `id` = dosya adı, `capabilities` registry'de tanımlı
  id'lere işaret eder, `platform_packs` pack dizinlerine; pack'ler — profil
  `platform_packs` listesinin açtığı `checklist.md` kalite modülleri
  (`platform-gate` skill okur).
- **Giremez:** Registry'de tanımsız capability id (profil/pack referansında);
  şema enum'u dışı surface (`capability.schema.json` `match.surfaces` enum'u
  registry ile birebir tutulur); pack içine script/kit kodu kopyası.
- **Denetim:** doctor.sh `check_capabilities` (capability + role-matrix
  şemaları, şema enum ↔ registry surface karşılaştırması, `validate_references`
  — rol/pack referansları) + `check_profiles` (şema + `id`↔dosya adı +
  capability/pack/skill referansları) + REQUIRED_FILES (capabilities/*) +
  unittest (`test_capabilities.py`, `test_profiles.py`, `test_macos_pack.py`,
  `test_variants.py`).

### B19 — Templates / automations / plans

- **Girebilir:** Hedef repo'ya kopyalanan şablonlar — `github-labels.json`
  (etiketler; registry `labels:` ile senkron), `ci-delivery.yml` (adaptation
  çıktısı örnek CI), `ecosystem-macos.yaml`; `automations/*.yml` — Orca
  zamanlanmış iş tanımları, **varsayılan kapalı** (`automations.py templates`
  listeler; kurulum/aktivasyon Orca tarafında ayrı onayla); `plans/P*.yaml` —
  dışarıda okunan referansın provenance'ı (kaynak repo + commit) + iç mekanizma
  haritası/eksik listesi.
- **Giremez:** Registry/sözleşme kopyaları (etiket listesi burada yaşar ama
  registry ile çelişirse doctor `check_labels` hata verir); automations'ın
  sessizce etkinleşmesi; plan dosyasına sözleşme/karar metni gizleme (P dosyaları
  referans haritasıdır, kaynak değil).
- **Denetim:** doctor.sh `check_labels` (`github-labels.json` ↔ registry
  `labels` + çekirdek etiketler, yinelenen ad kontrolü) + REQUIRED_FILES
  (`github-labels.json`) + unittest (`test_automations.py` — TEMPLATES glob
  ↔ dosya adları; `test_ci_workflow.py`; `test_surface_contract.py`;
  `test_rigor.py` + `test_doctor.py` P3.yaml'ı okur). plans/*.yaml için
  doctor'da şema denetimi **yoktur** — yalnız ilgili testler okur.

### B20 — Context / metrics / orchestrator

- **Girebilir:** `context/index.yaml` — yüzey → doküman/skill route indeksi
  (`routing.py` / `brief.py --route`; bilinmeyen anahtar, çözülemeyen yol veya
  pozitif olmayan weight brief'i exit 2 ile durdurur); `context/frequency.yaml`
  — sayımsal, kimliksiz sıklık tablosu (`.kit/context-metrics.jsonl`'den
  türetilir, `version` + `rows` taşır); `metrics/README.md` — closure
  raporunun zorunlu metrik tanımları (`closure.schema.json` ile kilitli);
  `orchestrator/` — orchestrator rol dosyaları (ROLE.md, how.md, …).
- **Giremez:** Kimlik/PII içeren kayıt (frequency yalnız sayım);
  `metrics/README.md` dışında yeni metrik alanı (şekli `closure.schema.json`
  belirler); `index.yaml`'e şema dışı anahtar (brief exit 2).
- **Denetim:** doctor.sh `check_schemas` (`context/frequency.yaml` —
  `context_metrics.report_frequency`) + REQUIRED_FILES + `check_links`
  (DELIVERY rglob `*.md` — orchestrator md dahil) + unittest
  (`test_brief.py` — route index ve geçersiz context → exit 2;
  `test_context_metrics.py`). `orchestrator/` registry agents denetiminin
  dışındadır (doctor registry agent listesinden `orchestrator`'ı çıkarır);
  denetimi yalnız link taramasıdır — ayrı şema/kapı yoktur.

### B21 — `.agents/skills/` (install çıktısı; makineye özel)

- **Girebilir:** `./install.sh`'in ürettiği proje seviyesi skill kopyaları
  (`.agents/skills/<name>/SKILL.md`); makineye özel kurulum durumu.
- **Giremez:** Elle kopyalama/düzenleme — kaynak daima `skills/`'tir
  (çakışmada `skills/` kazanır, kopya yalnız `./install.sh` ile tazelenir);
  `.agents/` gitignore'dadır, commit'e girmez; kopya güncel sayılır
  varsayılmaz.
- **Denetim:** `./install.sh --dry-run` + doctor.sh `check_installed_skills`
  (uyar-only: kaynak ile kopya farklıysa uyarır; `.agents/skills/` yoksa ya da
  `DEMIR_KIT_DOCTOR_IGNORE_INSTALLED=1` ise denetim sessizdir) + review. Bu
  repoda `.agents/skills/` dizininin kendisi yoktur.

## Audit paths (module × check)

| Modül | doctor | unittest | registry | guard |
|-------|--------|----------|----------|-------|
| `delivery/CONTRACT.md` | ✔ (version/contract) | ✔ | — | ✔ |
| `delivery/registry.yaml` | ✔ | ✔ | ✔ (tek kaynak) | ✔ |
| `delivery/schemas/` | ✔ (`--body`/`--issue`) | ✔ | ✔ (şema referansları) | ✔ |
| `delivery/policies/` | ✔ (link + tutarlılık) | ✔ | ✔ (quality-gates referansı) | ✔ |
| `delivery/protocol/` | ✔ (link kontrolü) | ✔ | ✔ (protocol referansları) | ✔ |
| `delivery/agents/` | ✔ (varyant + agent.yaml) | ✔ | ✔ (agent_variants) | ✔ |
| `delivery/runbooks/` | ✔ (pr-flow/adaptation/update — zorunlu dosya + link) | ✔ (test_ci_workflow, test_self_update, test_refactor) | — | ✔ |
| `delivery/scripts/` | ✔ | ✔ | ✔ (script yolları) | ✔ (G1 + risk) |
| `delivery/tests/` | ✔ | ✔ | — | ✔ |
| `delivery/capabilities/` + `delivery/profiles/` + `delivery/packs/` | ✔ (check_capabilities + check_profiles + check_files) | ✔ (test_capabilities, test_profiles, test_macos_pack) | ✔ (registry `capabilities:` / `profiles:` blokları — doctor doğrular) | ✔ |
| `delivery/templates/` + `delivery/automations/` + `delivery/plans/` | ✔ (templates/github-labels.json — check_files + check_labels) | ✔ (test_ci_workflow, test_surface_contract, test_automations, test_rigor/test_doctor — plans/P3.yaml) | — | ✔ |
| `delivery/context/` + `delivery/metrics/` + `delivery/orchestrator/` | ✔ (context/frequency.yaml — check_schemas; metrics/README.md — check_files; orchestrator md — link) | ✔ (test_brief — route index; test_context_metrics) | — | ✔ |
| `skills/` | ✔ (skill denetimi) | ✔ | ✔ (`skills.runtime`) | ✔ |
| `.agents/skills/` | ✔ (kopya denetimi) | — | ✔ (kaynak `skills/`) | — |
| `discovery/` | ✔ (link/ağ) | — | — | ✔ (kapsam) |
| `archive/v1.7/` | ✔ (legacy) | ✔ | — | — |
| `docs/` | — (kapsam dışı; link hedefi geçerli olmalı) | — | — | — |
| `plugins/` | — (doctor taramaz) | ✔ (test_orca_plugin; `gate.sh` plugins/ değişiminde Orca plugin süiti koşar) | — | — |
| `ecosystem.yaml` / `kit.config.yaml` | ✔ (wiring/version) | ✔ | ✔ | ✔ (kök common-path `*.yaml`) |

guard sütunu yalnız `guard.sh`'te tanımlı write-surface denetimini gösterir: G1 uygulama yüzeyi (bu repoda `factory.app_paths` yoktur, `kit.root: .` olduğundan varsayılan `delivery` + `skills`) ve `--issue N` çağrısında seal yüzeyi glob'larıyla (bu repoda kit.docs: `delivery/**`, `skills/**`, `discovery/**`, `.github/**`, `VERSION`, `install.sh` + kök common-path'ler `*.md`/`*.json`/`*.yaml`/… — `docs/**`, `plugins/**`, `archive/**`, `.agents/**` dışarıda); ✔ = modülün dosyaları bu glob'lara uyar, `—` = uymaz, ve bu sütun doctor'ın kapsamını değil yalnız guard'ın yüzeyini tarif eder.

`doctor.sh --strict` CI kapısıdır (warning = error). `gate.sh` davranış komutunu
koşar; `guard.sh` yazım yüzeyini sınırlar; `transition.sh` durum geçişlerinin tek
yazıcısıdır.

## Notes

- `cost-and-tiers.md` bu dokümanın parçası **değildir**; ayrı bir karar
  (#382 dışı) ve architect kapısının diğer kıyas temelidir.
- `ecosystem.yaml` ve `kit.config.yaml` bu repoda self-host wiring'dir;
  bir üründe aynı dosyalar ürünün kendi köküne aittir — kit bunları yamalamaz.
- Bu dosya bayatlarsa architect kapısı sessizce yanlış kıyas yapar; modül
  değişikliğiyle birlikte güncellenir, aksi halde PR reddedilir.
