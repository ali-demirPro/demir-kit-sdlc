# Changelog

## 2.28.0 — 2026-10-29

- **macOS desteği** — `platform.macos` capability, `macos-app` profili,
  `macos_app` sinyali ve `detect.py`'de pbxproj tabanlı ios/macos ayrımı;
  `init` macos yüzeyini doğru profile yönlendirir. Yedi rolün varyant
  haritaları tamamlandı.
- **Proje risk overlay** — `.kit/risk.yaml` ile projeye özel `auto_escalate`
  glob'ları eklenebilir (yalnız ekleme sınıfı); `guard.sh` ve `risk_filter`
  overlay'i okur, `doctor --product` biçimini doğrular. Vendor sync'ten
  etkilenmez.
- **Proje öncelikleri (I14)** — `policies/project-priorities.md`: design system
  uyumu, mimari koruma, plana sadakat, kalite zemini ve "uydurma yok" kuralı
  bağlayıcı. `kit.config.yaml product.priorities` beyanı `brief.py` ile her
  agent brief'ine taşınır; `seal.md` referans zorunluluğu getirir;
  `doctor --product` yolları doğrular.
- **Init upstream** — `init.py` artık `kit.upstream.git` yazar
  (`--upstream` ile değiştirilebilir); `runbooks/adaptation.md` etiket kurulumu
  için `templates/github-labels.json`'u referans verir.
- **Test** — macos tespiti, risk overlay, priorities doğrulama senaryoları;
  374 test.

## 2.27.1 — 2026-10-28

- **Sürüm drift denetimi** — `doctor` artık `kit.config.yaml` `kit.version` ve
  `AGENTS.md` sürüm başlığını `VERSION` ile hizalar; self-host wiring'deki
  sessiz kayma (2.26.1 / 2.26 vs 2.27.0) düzeltildi.
- **Verify yüzey fallback** — fingerprint yüzey bulamazsa `ecosystem.yaml`'da
  bildirilen yüzeyler yedek sayılır; docs/markdown self-host projelerinde
  `verify` artık geçer.
- **Hedef proje CI** — `delivery/templates/ci-delivery.yml` örnek workflow;
  `runbooks/adaptation.md`'de CI wiring ve PyYAML gereksinimi belgelendi.
- **Test** — sürüm drifti ve yüzey fallback senaryoları eklendi; 363 test.

## 2.27.0 — 2026-10-28

- **Self-improvement lane** — kit kendi kendini geliştirmede insan kapısı
  kalktı: `I13` "agent kendi kabulünü yazamaz" kuralının kapsamı ürün
  teslimatına daraltıldı; kit self-improvement'ta kabul `doctor --strict` +
  testler yeşilidir.
- **Öğrenim federasyonu** — `learnings.py` filo repolarından `learning`
  issue'larını hasat eder, 2+ projede tekrar eden dersleri genel kural
  adayına dönüştürür (--digest/--emit) ve beyaz listedeki ekleme sınıfı
  değişiklikleri (risk glob, eval senaryosu, skill notu) otomatik uygular
  (--apply). Kural azaltma/silme ve kod değişikliği otomatik yazılmaz,
  `learning` issue'suna düşer.
- **Fleet registry** — `delivery/fleet.yaml` beyne öğrenim taşıyan klon
  repoları kaydeder; `doctor` formatını denetler. Öğrenim şeması:
  `delivery/schemas/learning.schema.json`.
- **Test** — 356 test.

## 2.26.1 — 2026-10-27

- **CI gürültüsü** — `issue-doctor` artık taslak düzenlemelerde (`edited`/`opened`)
  çalışmıyor; yalnız etiket/kapanış olaylarında tetikleniyor. `agent-approved`
  anındaki seal hatası uyarıya düşer, `leaf-done`/`epic-done` denetimi sert kalır.

## 2.26.0 — 2026-10-27

- **Ölü kod temizliği** — kullanılmayan ürün şablonu kaldırıldı; `brief`
  komutu belgelendi; `web-product` legacy alias olarak sadeleştirildi.
- **Profil modeli** — kullanılmayan `default_entry`, `default_quality_tier`,
  `suggested_surfaces`, `checkpoint_templates` alanları kaldırıldı;
  `required_skills`, `extra_gates` ve `platform_packs` plan ve mühür
  doğrulamasında tüketiliyor; overlay listesi `product_class`'tan türetiliyor.
- **Komut birleşimi** — `detect`, `standards` ve `init` aynı paket yöneticisini
  kullanır (pnpm/yarn/bun/uv/poetry); monorepo taraması 2 seviyeye hizalandı;
  dağıtım doğru yüzeye yazılır.
- **Adopt** — vendored kit ile çalışır; boş projede yazmadan durur; `verify`
  bayat `AGENTS.md` bloğunu yakalar; `doctor` FLOW/CONTRACT/registry sürüm
  başlıklarını denetler.
- **Test** — 347 test.

## 2.25.0 — 2026-10-27

- **Monorepo tespiti** — kök yüzey yoksa 1–2 seviye alt dizinlerde manifest
  taranır (Node, Python, Flutter, Swift, Go, Rust); yüzey yolu gerçek dizin olur.
- **Güvenli komutlar** — alt dizin test komutları `(cd yol && ...)` alt
  kabuğunda birleşir; `node_modules`, `Pods`, `build` gibi dizinler atlanır.
- **Kök önceliği** — kök manifest varsa eski davranış korunur, nested tarama
  çalışmaz; aynı yüzey iki kez sayılmaz.
- **Test** — Flutter monorepo, web+API, node_modules ve kök-öncelik; 337 test.

## 2.24.0 — 2026-10-27

- **Tek komutla adopt** — `adopt.py` hedef projeye agentic SDLC kurar:
  `init` → eksikse `vendor_sync` → `AGENTS.md` standartları → read-only
  `verify`. Varsayılan dry-run; `--apply` yalnız hedef projeye yazar.
- **Güvenlik** — kaynak/hedef kit çakışırsa yazmadan reddeder; mevcut dosyalar
  ezilmez; ikinci çalıştırma idempotenttir.
- **Test** — dry-run, apply, AGENTS koruma, idempotency, overlap ve boş proje;
  327 test.

## 2.23.1 — 2026-10-27

- **Proje bağımsızlığı** — kabul kanıtındaki proje adları ve yerel yollar
  kaldırıldı; doğrulama web+API, iOS ve Flutter fixture'larıyla tanımlanır.
  Sistem hedef projeye çalışma anında yetenek enjekte eder, proje kimliği
  taşımaz.

## 2.23.0 — 2026-10-27

- **Uyarlama doğrulaması** — `verify.py` fingerprint, profil önerisi, capability
  seti ve standartları read-only doğrular; çok proje ve `--json` destekler.
- **Kabul** — web+API, iOS ve Flutter referans fixture'ları read-only doğrulandı;
  hedef proje adı veya yolu sistemde tutulmaz.
- **Test** — web+API, iOS, Flutter fixture, boş proje, yazmama, çok proje ve
  hata çıkış kodu; 318 test.

## 2.22.0 — 2026-10-27

- **Standart keşfi** — `standards.py` kök ve birinci seviye alt dizinlerde paket
  yöneticisini, test/tip/lint/biçim komutlarını ve stil dosyalarını bulur
  (Node, Python, Go, Swift, Rust). Komut yoksa uydurmaz.
- **AGENTS.md enjeksiyonu** — `--apply` yönetilen bloğu yazar; mevcut içerik
  korunur, tekrar çalıştırma idempotenttir, dosya yoksa oluşturulur. `--check`
  eksik veya bayat bloğu bildirir.
- **Test** — Node/Python/Go/Swift, çok dilli repo, yanlış pozitif, koruma,
  idempotency ve check; 308 test.

## 2.21.0 — 2026-10-27

- **Profil kompozisyonu** — Profil artık tek seçim değil; repo birden fazla base
  (`web-app`, `ios-app`, `android-app`, `flutter-app`, `api-service`, `cli`,
  `library`, `game`, `landing`, `data-ml`) ve overlay (`auth`, `payments`,
  `offline`, `multi-tenant`, `regulated`, `high-scale`) barındırabilir.
- **`factory.profiles`** — capability, platform pack, ek gate ve skill'ler
  birleşir; `default_profile` seçili profillerden biri olmalıdır.
- **`profiles.py`** — compose/check CLI; `kit init` fingerprint'ten çoklu profil
  önerir; resolver profil capability'lerini beyanla birleştirir; doctor profil
  şemasını, referansları ve default'u doğrular.
- **Kanıta dayalı dağıtım** — base profiller store dağıtım capability'si
  üretmez; `distribution.app_store`/`play` yalnız algılanan kanıt veya açık
  beyanla gelir. `init` `.kit/capabilities.yaml` içine yalnız algılanan
  capability'leri yazar; profil katkısı resolver'da birleşir.
- **Geriye uyum** — profilsiz ve 2.20'nin `mobile-app`/`unknown` default'lı
  eski ürünleri geçerli kalır; ürün şablonu `profiles: [web-app]` ile gelir;
  `web-product` legacy takma ad olarak kalır.
- **`adapt --apply`** — yalnız proje kararı olan include/exclude yazılır;
  profil capability'leri dosyaya sabitlenmez, resolver'da birleşir.
- **Test** — web+api+auth, web+ios, overlay-only, bilinmeyen profil, legacy
  default, profilsiz resolver birleşimi, store-kanıt ayrımı ve adapt
  kalıcılığı; 290 test.

## 2.20.0 — 2026-10-27

- **kit init** — `init.py` fingerprint'ten `kit.config.yaml`, `ecosystem.yaml`,
  `.kit/capabilities.yaml` ve `scripts/gate-behavior.sh` üretir.
- **Güvenli apply** — varsayılan dry-run; `--apply` yalnız yeni dosyaları yazar,
  mevcutları atlar; `--force` açık istekle üzerine yazar.
- **Test** — web/iOS app_store, dotted repo, no-write, skip, force; 267 test.

## 2.19.0 — 2026-10-27

- **Project fingerprint** — `detect.py`: package/Next/React, Swift/Xcode, Gradle/
  Android, Flutter, Python, Docker ve CI sinyallerinden stack/surface/
  distribution/test/app path/risk hotspot üretir.
- **Read-only** — detect hiçbir dosya yazmaz; `kit init` için girdi.
- **Test** — web/iOS/Android/Flutter/Python temp projeleri; 256 test.

## 2.18.0 — 2026-10-27

- **Eval runner** — `eval.py`: eval tablolarını parse eder, her variant için
  en az 10 senaryo, benzersiz ID ve dolu expected/fail alanı ister.
- **Results** — `--results` tüm senaryoların pass/fail/skip sonucunu ister;
  eksik/fazla/duplicate/fail reddedilir. `--template` iskelet üretir.
- **CI** — `delivery-doctor` workflow `eval.py --check` çalıştırır; branch
  protection bunu required check içinde tutar.
- **Test** — 250 test.

## 2.17.0 — 2026-10-27

- **Designer variants** — a11y, performance, privacy, i18n, analytics; 5 yeni
  doküman, 2 eval seti.
- **Tester variants** — auth/payments, data/offline, analytics/i18n,
  security/privacy, a11y/performance, observability, delivery; 7 yeni doküman,
  3 eval seti.
- **Coverage** — designer/tester rol matrisi ↔ variant gap'i sıfır; eval
  setlerinde en az 10 senaryo testle zorlanır.
- **Test** — 245 test.

## 2.16.0 — 2026-10-27

- **Capability-aware plan** — `orca_plan` capability setini, aktif variant
  dokümanlarını, variant gap'lerini ve risk tabanını taşır; implementer task
  spec'i ilgili variant'ı okur.
- **Reviewer planı** — UI CP designer, high/critical/auth/payments security +
  architect, distribution release/marketing reviewer'ları plana eklenir.
- **Test** — web/iOS/API/high-risk/critical planları; 243 test.

## 2.15.0 — 2026-10-27

- **Capability enforcement** — `doctor` capability `risk_floor`'u seal riskiyle
  karşılaştırır; yüksekse seal riski yükseltilmeden geçmez. High/critical
  leaf'te variant gap varsa `leaf-done` engellenir.
- **Risk glob** — `guard.sh` artık `registry.yaml risk.auto_escalate` glob'larını
  kullanır; hardcoded auth/payments regex'i kaldırıldı.
- **Matching** — seal `intent` capability eşleşmesine dahil edildi (brief ve
  doctor aynı metni kullanır).
- **Test** — risk floor, high-risk gap, registry glob; 237 test.

## 2.14.0 — 2026-10-27

- **Branch protection** — `protect_main.sh` main için PR + `delivery-doctor`
  required check, `enforce_admins`, force-push/deletion kapalı korumayı uygular;
  `--check` doğrular. Koruma canlı repo'da uygulandı.
- **PR runbook** — branch protection artık UI adımı değil, kodla uygulanan
  kontrol.
- **Test** — protection scripti davranış testleri (pass/no-PR/admin bypass); 234 test.

## 2.13.0 — 2026-10-27

- **Human acceptance** — `epic-done` artık insan-authored `demir-kit-accept`
  comment'i ister; agent'ın `--accept` string'i tek başına yetmez. Bot/agent
  yazarı reddedilir. Transition kabul bloğu yazmaz.
- **Epic closure integrity** — tüm child'lar `leaf-done`/`deferred` olmalı;
  closure `metrics.leaf_count` child sayısıyla eşleşmeli. Doctor ve transition
  bunu zorlar.
- **Tests** — human/bot, açık child, leaf_count uyuşmazlığı; 225 test.

## 2.12.0 — 2026-10-27

- **Adapter** — `.kit/capabilities.yaml` (`include`/`exclude`) ve `adapt.py`:
  proje capability setini açıkça yönetir; varsayılan dry-run, `--apply` yazar.
- **Diff** — capability/rol/variant/gap/risk farkı; web→web+Android, iOS→web ve
  capability kaldırma senaryoları.
- **Resolver** — declared include/exclude derived set ile birleşir; brief yalnız
  aktif seti yükler.
- **Doctor** — `doctor --product` bilinmeyen declared capability'yi reddeder.
- **Runbook** — `delivery/runbooks/adaptation.md`; 215 test.

## 2.11.0 — 2026-10-27

- **Resolver** — `resolver.py`: ecosystem surfaces + leaf seal + capability
  registry'den aktif capability, rol, variant, pasif variant, gap ve risk tabanı.
- **Brief** — capability/variant özeti; yalnız aktif variant dokümanları yüklenir.
  Web-only projede iOS/Android dokümanları, iOS-only projede web dokümanları
  yüklenmez.
- **Doctor** — capability'nin zorunlu kıldığı roller evidence için kabul edilir
  (ör. web leaf'inde security).
- **Tester API/CLI variant** — contract, authz, idempotency, rate limit ve CLI
  çıkış kodu testleri; API-only projede variant gap'i kapatıldı.
- **Test** — web/iOS/web+iOS/API senaryoları; 203 test.

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
