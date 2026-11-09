# Changelog

## 2.63.0 — 2026-11-09

- **Risk tabanı değişmezi (Epic #290, #327)** — CONTRACT'ta çakışan ikinci
  `I11-I14` bloğu `I20-I23` olarak yeniden numaralandı; `I24` rigor seviyesinin
  risk tabanını, `auto_escalate` glob'larını veya insan kapısını
  düşüremeyeceğini yazar. Gating reviewer sayısı yalnız riskten gelir
  (low/medium 1, high/critical 2).
- `learnings.py` epic-done insan kabulü atfı `I22`'ye bağlandı;
  Self-improvement lane aynı numarayı kullanır.
- Testler minimal/standard/full seviyelerinde reviewer sayısının ve
  high/critical insan kapısının değişmediğini gerçek `rigor` ve `routing`
  fonksiyonlarıyla kanıtlar (`test_doctor.py`).
- Sürüm 2.63.0.

## 2.62.0 — 2026-11-09

- **Otonomi ve delegated kabul (Epic N, #283)** — `delivery/policies/autonomy.md`
  eşikleri (A2 otonom), durma koşullarını (A0 insan kapısı), vekâleten kabul
  sınırını (A1) ve dönüş özetini tanımlar; CONTRACT Yürütme bölümü ve registry
  politikaya bağlanır.
- Sahip yokken `low`/`medium` leaf, review, closure ve PR vekâleten kapatılır ve
  `delegated: coordinator` ile işaretlenir; geri dönülemez iş ve ürün
  teslimatında epic kabulü insanda kalır.
- Sürüm 2.62.0.

## 2.61.0 — 2026-11-08

- **Orca'ya devret (Epic N, #277)** — kit makine kapısı olmaktan çıktı:
  `next-leaf --claim`, `orca_wave` ve `review_wave` artık `resources.blocked`
  yüzünden exit 3 vermez; `resources.py` yalnız rapor üretir, `--check` her
  durumda 0 döner. Orca hep var sayılır, kaynak yönetimi Orca'nındır.
- Otomatik reaper ve `worker_cleanup` kaldırıldı; worker kapatma yalnız
  `orca orchestration worker-release` ile, `retained` kaydına dokunmadan.
- `hygiene.py` artık simülatör silmez/`simctl` ayrıştırmaz; yalnız DerivedData
  temizler. `--simulators` bayrağı kaldırıldı; simülatör yaşam döngüsü
  `orca emulator` komutlarında.
- `resources.py` simülatör sayımını bıraktı; simülatör ölçümü Orca'ya ait.
- Sürüm 2.61.0; `brief.py` makine satırı bilgilendirme olarak güncellendi.

## 2.60.0 — 2026-11-08

- **Makine bütçesi (Epic A)** — paylaşılan `DerivedData` (`detect.py` + skill'ler),
  `resources.py` makine freni (RAM/compressor/load/simülatör/ağır iş), boşta worker
  reaper, `budget.py` ağır iş bütçesi, `gate-cache` (tree hash + TTL), `hygiene.py`
  güvenli temizlik.
- **Epic hızı (Epic B)** — epic içi paralel leaf (dosya kesişimi yoksa 2),
  `severity: blocking|nit` ile review yakınsaması, 60 dk onay timeout'u
  (`approval_sweep.py`), review paketinde kapı kanıtı, `gate --fast` tiering.
- **Ölçüm ve bağlam (Epic C)** — `.kit/cycle.jsonl` gerçek geçiş defteri,
  `audit.py` filo denetimi, 200k/300k bağlam sınırı, oturum hijyeni, salt-okur
  kapı (`--fix`), genel anahtar kelimelerin risk tabanını şişirmesi düzeltildi.

## Unreleased — 2026-11-08

- **Epic içi paralel leaf** — `next-leaf.py` aynı epic'te dosya kesişimi
  olmayan iki leaf'i aynı anda verebilir (`--max-parallel`, varsayılan 2).
  Kesişen leaf bekler ve gerekçe tek satır yazılır; `--list --json` çıktısı
  `{eligible, skipped}` sözlüğüne döndü.

## 2.59.4 — 2026-11-05

- **Kalıcı plugin odağı** — terminal → workspace eşlemesi artık
  `agents.terminals.v1` anahtarında `orca.storage`'da tutulur: worker yeniden
  başlasa da odak korunur. Eşleme `identity:` id, `<repo>::/yol` ve çıplak yol
  biçimlerini çözer; odak sırasına odaklı ajanların `terminalId`'leri eklendi.
- **Sınırlı ve temiz harita** — en fazla 200 kayıt, 30 gün TTL, silinmiş
  workspace temizliği (`workspace.list.truncated` korumalı), bozuk/sürümü eski
  kayıt atma ve yalnız değişiklikte 1 sn debounce'lu yazma. Harita boşsa
  `storage.delete` ile anahtar silinir.
- **Odak yoksa görünür özet** — snapshot üstüne `live` ve `active` alanları
  eklendi. Odak çözülemezse hata yerine `odak çözülemedi` uyarısı, panelde nötr
  bilgi satırı, durum çubuğunda `N aktif · M proje` / `N çalışıyor · M proje`
  gösterilir. `status.snapshot` hiçbir koşulda istisna fırlatmaz.

## 2.59.3 — 2026-11-05

- **Değişen dosyaya göre CP kapısı** — `delivery/scripts/gate.sh` (python
  `gate.py`) sürümü yalnız gerekli suite'i koşar: `delivery/tests/` altındaki
  değişiklik unittest'i, `plugins/` altındaki değişiklik Orca eklenti suite'ini
  tetikler; doctor her zaman ve kapı olarak çalışır.
- **Sembolik bağ eşleşmesi** — `projectPath` karşılaştırması artık önce
  `realpathSync` ile gerçek yolu alır: sembolik bağ ya da `..` üzerinden verilen
  ayar yolu da aynı workspace kartını bulur. Yol diskte yoksa normalize
  karşılaştırma korunur; önbellek anahtarı ve `agentEventTarget` değişmedi.

## 2.59.2 — 2026-11-05

- **Panel odağı ve ajan eşlemesi** — `workspace.changed` ve
  `agent.status.changed` artık tahminle kart seçmez: odak sırası olay
  id/path (varsa), terminal eşlemesi, benzersiz ad; hiçbiri tutmazsa
  `focused: null` ve hiçbir karta ajan yazılmaz. Ajan olayı workspace
  taşımıyorsa eski odak yeniden kullanılmaz, tam tazeleme yapılır; başka
  workspace'in olayı hiçbir kartı değiştirmez. Ajanlar yalnız `agents.list`'in
  odaklı workspace kartına yazılır; odak worktree'ye düşerse dedupe o kaydı
  korur.
- **Host'a duyarlı dedupe** — `workspace.list.hostId` hem kart anahtarına hem
  30 saniyelik önbellek anahtarına (`project:<host>::<yol>`) girer: iki hosttaki
  aynı mutlak yol ayrı kart kalır. `hostId` yoksa workspace id'sinin `::` ön eki
  host dilimi olur (`identity:<host>`); o da yoksa kayıtlar birleşebilir
  (bilinen sınır).

## 2.59.1 — 2026-11-05

- **Yanıt şekli denetimi** — `compat.py` üç salt-okunur Orca komutunun
  (`run-current`, `run-list`, `task-list`) `result` şeklini doğrular; drift
  `orca <komut>: yanıt şekli — <ayrıntı>` olarak raporlanır. `run-current` hem
  `result.runId` hem eski `result.run.id` biçimini kabul eder; bağlı Run yoksa
  prob atlanır, problar bağımsız çalışır ve `orca` yoksa sessizce geçilir
  (`--no-shapes` ile kapatılır).
- **Doctor** — kit modunda `doctor_compat.check_compat` şema ve şekil
  sorunlarını aynı hata listesine yazar (`--product` etkilenmez); kontrol
  `--explain compat` ile listelenir. Sözleşme
  [Orca protokolü](delivery/protocol/orca.md) içindeki "Yanıt şekli"
  bölümünde. Sürüm drift yardımcısı satır bütçesi için
  `doctor_version.py`'ye taşındı (davranış aynı).

## 2.59.0 — 2026-11-05

- **Profil kaynakları** — `profiles.py --resolve --json` birleşik profili ve her
  değerin kaynağını (`path:line`) döner: base, overlay, pack, kapı ve risk
  kuralı. `--paths` risk eşleşmesini besler; komut hiçbir şey yazmaz.
- **Doctor açıklaması** — `doctor.py --explain <ad>` tek kontrolün modunu
  (`kit`/`--product`), etkinliğini ve tanım satırını yazar; `--explain gates`
  etkin kapı setini kaynaklarıyla listeler. Kontrol koşmaz.
- **MCP `explain`** — salt-okunur altıncı araç; `name` ile `doctor --explain`,
  yoksa `profiles --resolve --json` çağırır (`project`, `paths` opsiyonel).
  [MCP protokolü](delivery/protocol/mcp.md) altı aracı ve açıklama sözleşmesini
  anlatır.

## 2.58.0 — 2026-11-04

- **Submodule modu** — `self_update.py` artık üç modu ayırır (`self` →
  `submodule` → `vendored`); `.gitmodules` içinde tanımlı ama başlatılmamış
  submodule de `submodule` sayılır, `vendored`'a düşmez. Plan
  `git submodule update --init`, `kit.config.yaml` sürümü ve
  `doctor --product` üretir, commit atmaz
  (`pointer değişti; ürün reposunda commit'le`).
- **Ref güvenliği** — `--ref` boş, boşluk içeren, `-` ile başlayan, `..`
  içeren ya da refspec meta karakteri (`:`, `*`, `^`, `~`, `@`, ters bölü)
  içeren değerleri plan hatası (`ok:false`) olarak reddeder; submodule'de
  `--remote` olmadan init + `fetch --depth 1` + `checkout --detach` ile o
  commit'e sabitlenir.
- **Config** — `kit.config.yaml` yeniden yazılmaz; yalnız `kit.version` satırı
  güncellenir, yoksa eklenir (yorumlar ve CRLF korunur).
- **Runbook** — [güncelleme runbook](delivery/runbooks/update.md) üç modu,
  submodule örneğini ve `git submodule update --init` tabanlı geri dönüşü
  anlatır.

## 2.57.0 — 2026-11-04

- **MCP yüzeyi** — kit komutları (`status`, `brief`, `doctor`, `next_leaf_list`,
  `guard`) stdio MCP sunucusundan salt-okunur açılır; araç tanımları
  `readOnlyHint` taşır, mutasyon aracı yoktur.
- **Orca plugin** — portföy paneli (liste + düz detay), iki durum çubuğu öğesi,
  epic/leaf aksiyonları; kabul ve claim yalnız kit scriptleriyle yürür, panel
  repoya yazmaz.
- **Status sözleşmesi** — `epics[].checkpoints[]`, `epics[].leaves[]` ve
  `project.repo_root` alanları; eski `{done,total}` biçimi çökmeden okunur.
- **Self-update** — `self_update.py`: dry-run plan, `--apply`, `self`/`vendored`
  mod, `--source`, `--skip-skills`; tek komutla güncelleme
  ([runbook](delivery/runbooks/update.md)).

## 2.56.0 — 2026-11-02

- **Fail-closed giriş** — `next-leaf` kaynak dosyaları kirli ve sealed leaf
  yoksa `BLOCKED` yazar, exit 1 döner; “no work” yalnız değişiklik yokken.
- **Doctor** — ana dalda kirli kaynak dosyası hata; epic dalında uyarı. Ürün
  reposunda hook yoksa uyarı.
- **Hook kurulumu** — `init.py --apply` pre-commit (guard) ve pre-push (main
  push yasağı) hook’larını kurar; yabancı hook’u ezmez, idempotenttir.
- **CI şablonu** — `main`’e doğrudan commit’i reddeden `process-gate` işi;
  merge PR commit’ine izin verir.

## 2.55.0 — 2026-11-02

- **Miras modeli hata yakalama** — `session_model` eksik CLI (`OSError`),
  zaman aşımı (`TimeoutExpired`) ve bozuk yanıtta `None` döner; plan düşmez,
  model geçirilmez. Mirasın `orca_plan` görevine geçişi test edildi.

## 2.54.0 — 2026-11-02

- **Kısmi worker ölçümü** — kayıtlı ve kayıtsız worker karışıksa closure ölçülen
  alanları yazar ve `worker_partial: true` işaretler; hiç ölçüm yoksa alanları
  yazmaz. Şema, metrics README ve runbook güncel.
- **Deferred listesi** — defer edilen child'lar closure `deferred` listesine
  issue + gerekçe ile yazılır; boş liste varsayımı kalktı.

## 2.53.0 — 2026-11-02

- **Paralel worker eşleştirme** — `review_wave` başlattığı worker'ın çalışma
  kimliğini `.orchestration/worker-sessions.json`'a yazar; `usage.py --run`
  yalnız bu kaydı kullanır ve paralel reviewer'ları `exact` ölçer. Kayıt yoksa
  `unavailable` döner; tahminle maliyet yazılmaz. Tek `--dispatch` pencereyle
  dener, belirsizse `unavailable` kalır.
- **Metrik notu** — metrics README kayıt kuralını ve sınırını yazar.

## 2.52.0 — 2026-11-02

- **Model nötrlüğü** — kit varsayılan olarak `--model`/`--effort` geçirmez;
  worker oturum/ortam modelini kullanır. `orca.inherit_session_model: true`
  koordinatörün modelini açıkça devralır; `role_defaults` model/effort yalnız
  `orca.allow_model_override: true` ile uygulanır.
- **Koruma** — `doctor` (`model policy`) bayraksız rol model/effort ayarını hata
  sayar; `opencode2` effort ayarını uyarı olarak işaretler.
- **Politika** — `delivery/policies/model-selection.md`, registry, CONTRACT ve
  AGENTS bağlantıları; `model_policy.py` tek karar noktası.

## 2.51.0 — 2026-11-02

- **Seal lint** — `seal_lint.py --body FILE` mühür metnini denetler: belirsiz
  ifade + gözlenebilir sonuç yokluğu, çalıştırılabilir iz taşımayan unit/gate
  case'i, tekrarlı case ID, bilinmeyen AC/CP referansı. `doctor --body` aynı
  lint'i çalıştırır; hatalar bloklar, uyarılar yalnız `--strict` ile.
- **Mühür protokolü/skill** — `seal.md` ve `work-package` lint uyarılarını
  anlatır; geçmiş issue'lar uyarıyla geçer, bloke edilmez.

## 2.50.0 — 2026-11-02

- **Paralel reviewer dalgası** — `review_wave.py --issue N --cp CP-x --commit SHA
  --reviewers a,b --apply` reviewer'ları tek dalgada paralel Orca worker olarak
  başlatır, paketi (≤12 KB) verir, bekler, `approved:` verdict'lerini toplar ve
  biten terminalleri serbest bırakır. Hepsi onaylamazsa exit 1.
- **Review paketi** — `packet_for()` ayrıştırıldı; wave ve CLI aynı üreticiyi
  kullanır.
- **Protokol/skill** — execution review adımı ve `adversarial-review` skill'i
  dalgayı anlatır.

## 2.49.0 — 2026-11-02

- **Closure otomasyonu** — `closure.py --issue <epic>` leaf/cp sayısını,
  etiket zamanlarından lead time'i, run'dan worker sayılarını ve claim
  snapshot'larından koordinatör deltasını hesaplayıp `demir-kit-closure` bloğu
  üretir. `--post` yazar ve doctor düşerse yorumu geri alır.
- **Koordinatör metrikleri** — closure şemasına `coordinator_tokens_in`,
  `coordinator_tokens_out`, `coordinator_cache_read`, `coordinator_cost_usd`
  eklendi; metrics README ve runbook güncel.
- **Oturum uyuşmazlığı** — snapshot oturumu bugünkü oturumla eşleşmezse
  koordinatör sayıları `unavailable` sayılır, yanlış epic'e yazılmaz.

## 2.48.0 — 2026-11-02

- **cp-close tek adım** — `cp_close.py --issue N --cp CP-x --evidence <yaml>`
  planı gösterir; `--apply` sırayla gate → evidence yorumu → `doctor --issue`
  doğrulaması → Orca checkpoint çalıştırır. Gate düşerse hiç yazmaz; doctor
  doğrulaması düşerse yorumu siler ve exit 1 verir. Evidence fenced veya düz
  YAML olabilir; cp/issue/status uyuşmazlığı yazmadan reddedilir.
- **Protokol** — execution CP döngüsü kapanışı bu scripte bağlar.

## 2.47.0 — 2026-11-02

- **Review paketi** — `review_packet.py --issue N --cp CP-x --commit SHA` dar
  bir paket üretir: CP brief, AC/test satırları, açık bulgular ve diff (varsayılan
  12 KB). Reviewer tüm repoyu okumaz; `--delta <base>` ile fix sonrası yalnız
  aralık diff'i incelenir. `--json` / `--write` çıktı verir, `--max-chars` diff'i
  kısaltır.
- **Delta inceleme** — `adversarial-review` skill'i ve execution protokolü
  paketle başlamayı, fix sonrası yalnız delta + açık bulguları görmeyi anlatır.
- **brief** — `render_cp_brief(..., include_evidence=False)` ile reviewer
  paketinde worker evidence iskeleti yer almaz.

## 2.46.0 — 2026-11-02

- **Worker token/maliyet sayısı** — `usage.py --dispatch <id>` bir worker'ın
  worktree'sindeki OpenCode çalışmasını dispatch zaman penceresiyle eşler ve
  token/maliyet döndürür; eşleşme yoksa `unavailable`. `usage.py --run <id>`
  run'daki tüm worker'ları toplar (`worker_count`, `tokens_in`, `tokens_out`,
  `cache_read`, `context_peak`, `cost`).
- **Closure metrikleri** — şemaya opsiyonel `worker_count`, `tokens_in`,
  `tokens_out`, `cache_read`, `context_peak`, `cost_usd` eklendi; metrics
  README ve closure runbook sayıların nereden alınacağını yazar. Eski closure
  kayıtları geçerli kalır.
- **Worker temizliği** — yeni `worker_cleanup.py --run <id> --apply` biten
  worker pencerelerini serbest bırakır; `user_takeover` ve devam eden worker'a
  dokunmaz. `worker_done` sonrası çağrı execution protokolüne eklendi.

## 2.45.0 — 2026-11-02

- **Bağlam bütçesi** — yeni `delivery/policies/context-budget.md`: epic başına
  yeni bağlam (epic'ler arası `session move` yasak), koordinatör salt-okur,
  dosyayı bir kez ve dilimle okuma, araç çıktısı sınırı, CP sınırında compaction.
  Eşikler: 120k uyarı, 200k duruş. Ölçüm: dogfood'da tek bağlam 823k token'a
  çıkmış, adım maliyeti 8,5x artmıştı.
- **CP brief** — `brief.py --cp CP-1` altı KB'lık kompakt brief üretir (kapsam,
  o CP'nin AC/test satırları, gate komutu, evidence iskeleti, dosya listesi).
  `orca_plan.py` bunu worker spec'ine gömer ve `CONTRACT.md` /
  `quality-gates.md` dosyalarının tamamını okumayı yasaklar; worker soğuk
  başlangıcı 11 dokümandan brief + en fazla iki dilime iner.
- **Kayıt** — politika `registry.yaml → policies.context_budget`, `CONTRACT.md`
  ve `AGENTS.md` üzerinden bağlı; doctor link/registry kontrolleri yeşil.

## 2.44.0 — 2026-11-01

- **Skill kurulumu çağıran dizine** — `install.sh` başta `cd "$ROOT"` yapıyordu;
  `skills add` proje hedefini çalışma dizininden aldığı için ürün reposunda
  skill'ler `demir-kit/.agents/skills` içine (submodule) kuruluyordu. Artık
  çağıran dizinde `kit.config.yaml` varsa kurulum oraya yapılır
  (`Install dir: …` çıktıda), yoksa kit köküne. Submodule içinden çağrılırsa
  bir üst dizindeki ürün köküne kurulur. Self-host davranışı değişmedi.
- **Kuru çalıştırma** hedef dizini yazar; iki senaryo (ürün, düz dizin) test
  edilir.

## 2.43.0 — 2026-11-01

- **Yüzey kapısı kademelendi** — `ui: true` olan yüzeyde `snapshot` zorunluluğu
  artık beyan edilen karşılaştırma moduna bağlı: `ui_compare` yok/`none` ise
  **uyarı**, gerçek mod ise **hata**. Önceki hâlde kanıt aracı henüz olmayan ürün
  ya `ui: false` yalanına ya da kit yamasına itiliyordu.
- **Tarihli muafiyet** — `gates.ui_waiver: { reason, until, issue }` geçiş
  döneminde snapshot eksikliğini uyarıya çevirir. `reason` string, `issue`
  pozitif tam sayı ve `until` en fazla 180 gün ileri olmak zorunda; süre
  dolunca hata. Snapshot geldikten sonra kalan muafiyet uyarı verir. Tarih
  karşılaştırması UTC'dir (geliştirici makinesi ile CI aynı günü görsün).
- **Tek yol** — kit ve ürün denetimi aynı `surface_gate_messages` yardımcısını
  kullanır; `check_ecosystem` ile `doctor --product` artık ayrışamaz.

## 2.42.0 — 2026-11-01

- **Üründe scoped skill kurulumu** — `install.sh --capabilities` artık
  `skill_scope`'a kit kökü yerine **ürün kökünü** verir (`--cwd`; ürün
  checkout'unda `kit.config.yaml` varsa o). Önceki hâlde ürünün
  `.kit/capabilities.yaml` dosyası hiç okunmuyordu, bu yüzden `mac-verify` ve
  `swift-stack` hiçbir üründe kurulmuyordu. Self-host davranışı değişmedi.
- **Üründe yüzey denetimi** — `doctor --product` her yüzey için
  `surface_gate_errors` çalıştırır: `gates.ui: true` olan yüzey `snapshot`
  komutu olmadan geçmez, `ui`/`ui_compare` tipleri doğrulanır.
- **`package.json` uyarısı** — yalnız node/javascript/typescript stack'i olan
  projelerde aranır; Swift gibi projelerde gürültü yapmaz.

## 2.41.0 — 2026-11-01

- **Skill lint kenar durumları** — kaçışlı boşluklu link hedefi doğru çözülür;
  protokol-göreli (`//host`) link dış sayılır; satır içi kod spanındaki link ve
  `<!--` taranmaz; dipnot tanımı (`[^1]:`) link sayılmaz.
- **Olumsuzluk** — cümle başına kadar genişletildi ve Türkçe sonek
  (`… kullanma`, `… gerekmiyor`) yakalanıyor.
- **Son bölüm** — girintili ATX (`   ## Next`) ve kısa setext (`--`) başlıkları
  artık ihlal sayılır.

## 2.40.0 — 2026-11-01

- **`doctor.py` ayrıştırıldı (refactor)** — skill lint yardımcıları
  `doctor_skills.py`'ye, yüzey sözleşmesi `doctor_surfaces.py`'ye taşındı.
  `doctor` aynı isimleri yeniden dışa aktarır; arayüz ve davranış değişmedi.
  Dosya 1975 → 1787 satır.
- **Refactor kanıtı** — `verification.refactor` ile baseline/after aynı test
  sonucunu veriyor (`unchanged: true`), dosya sayısı git'ten ölçüldü.
- **Regresyon testi** — modül varlığı, arayüz, satır eşiği ve lint davranışı
  `test_doctor_modules.py` içinde.

## 2.39.0 — 2026-11-01

- **Kalan üç rolde macOS varyantı** — devops, pazarlama/mağaza ve inceleme
  rolleri artık `variants/macos.md` + `evals/macos.md` yüklüyor. Önceki hâlde
  mobil doküman (TestFlight, cihaz matrisi) geliyordu.
- **Resolver temiz** — macOS yüzeyi için `mobile.md`/`ios.md` yüklenmiyor;
  alias lint bu üç rolde de devrede.
- **Regresyon testleri** — eşleme, yedi bölüm, 10 senaryo, eval bütünlüğü ve
  resolver çıktısı test edilir.

## 2.38.0 — 2026-11-01

- **Yüzey sözleşmesi** — `ecosystem.yaml` `gates` altında `selftest` ve
  `snapshot`/`snapshot_pages` tanımlanabilir. `gates.ui: true` olan bir yüzey
  `snapshot` komutu olmadan geçemez; `doctor` bunu `ecosystem` kontrolünde
  arar. Görsel kanıt üretemeyen UI yüzeyi `ready: false` olur.
- **`ecosystem-macos.yaml` şablonu** — üç komutu (behavior, selftest, snapshot)
  doldurulmuş örnekle gösterir; `snapshot_pages` listesi dahil.
- **`ui-gate` `unchanged` modu** — `entry.kind: refactor` + `gates.ui: true`
  olduğunda mod otomatik `unchanged`: aynı viewport/seed/appearance ile aynı
  snapshot hash'i beklenir; tek piksel farkı `comparison_valid: false` üretir ve
  `ui_unchanged` kanıtını düşürür.
- **health-check** — snapshot/selftest maddeleri eklendi, numaralandırma
  sıralandı.

## 2.37.0 — 2026-11-01

- **Capability'ye bağlı skill'ler** — `registry.yaml` `skills.scoped`:
  `platform.macos` → `mac-verify`, `swift-stack`. Bu iki skill yalnız macOS
  capability'si bildiren projelerde kurulur; web projesinde gürültü olmaz.
- **`mac-verify`** — macOS kanıt sözleşmesi: `behavior`/`selftest`/`snapshot`
  komutları, `/tmp` store, light+dark, inaktif pencere kuralı, refactor
  `ui_unchanged` modu.
- **`swift-stack`** — Swift 6 izolasyonu, SwiftData geçişi, AppKit köprüsü sınırı,
  CLI build/imza (içten dışa) ve tanılama tuzakları.
- **`install.sh --capabilities`** — `skill_scope.py` ile projenin
  `.kit/capabilities.yaml` bildirimine göre runtime + scoped skill listesi
  üretir; `--dry-run` doğru listeyi basar.
- **`doctor` `scoped skills`** — scoped skill dosyası var mı, aynı skill iki
  capability'de mi, runtime ile çakışıyor mu denetlenir.

## 2.36.0 — 2026-11-01

- **`apple-macos` pack** — macOS yüzeyi için 14 maddelik platform checklist'i:
  menü çubuğu, kısayol, toolbar, sidebar, pencere, kontrol ölçüsü, tipografi,
  erişilebilirlik, Liquid Glass (yalnız macOS 26+ ve functional layer), sandbox,
  imza/notarization, güncelleme kanalı, veri/migration, gizlilik. 10–12. maddeler
  Apple dağıtım belgelerine, diğerleri HIG sayfalarına dayanır. `apple-hig` ve
  `apple-a11y` içindeki 44×44 pt kuralı dokunmatik platformlara daraltıldı;
  macOS için bu pack geçerli.
- **`distribution.direct`** — App Store dışı dağıtım capability'si: `dmg`,
  `notarize`, `notarization`, `sparkle` değerleriyle aktifleşir; risk tabanı
  `medium`. Önceki durumda doğrudan dağıtım için capability yoktu, yani
  notarization ve güncelleme kanalı kanıt olarak istenmiyordu.
- **İnsan kapısı zorlanıyor** — `gates` alanında `human` bildiren bir capability
  aktifse, `package_version: 4` seal'inde en az bir checkpoint `gates.human: true`
  olmak zorunda; `doctor` bunu denetler.
- **Rol kapsamı** — `devops` (expert), `security` (practitioner), `tester`
  (practitioner). `release` ve `documenter`'ın `agent.yaml` dosyası olmadığı
  için resolver bu rollere capability'ye özgü **varyant dokümanı** veremiyor;
  temel roller dokümanları yine yüklenir. Varyant haritası üç rolle sınırlı;
  `release` rolünün dağıtım onayı akışı ayrı iş (insan kapısı) olarak yürür.
- **Geçiş notu** — 2.36 öncesi mühürlenmiş `package_version: 4` leaf'lerde
  `gates.human: true` CP yoksa `doctor --issue` artık hata verir; kural
  geriye dönük uygulanır.
- **Playbook'lar** — `devops/variants/direct.md` (paketleme, imza, notarization,
  kanal, geri dönüş), `tester/variants/direct.md` (spctl/stapler doğrulaması),
  `security/variants/direct.md` (imza zinciri, entitlement, appcast).
- **`macos-app` profili** artık `apple-macos` pack'ini listeliyor.

## 2.35.0 — 2026-11-01

- **macOS varyantları** — `designer`, `developer`, `tester`, `architect` için
  `variants/macos.md`. Önceki hâlde `platform.macos` iOS/mobile dokümanına
  işaret ediyordu; macOS leaf'i iPhone ekran matrisi ve XCUITest talimatı
  alıyordu.
- **Alias lint** — `variants.py`, kendi `macos.md` dosyası olan bir rolde
  `platform.macos` eşlemesi başka dosyaya bakıyorsa hata verir. Paylaşımlı
  doküman kullanan roller (security, devops, marketing) etkilenmez.
- **Regresyon testleri** — dört rolün eşlemesi, yedi bölümlü doküman şablonu,
  alias reddi ve `resolver` çıktısında `ios.md` bulunmaması test edilir.

## 2.34.1 — 2026-11-01

- **Epic worktree kapısı** — `epic_worktree.check()` ana çalışma dizinini
  `main_root()` ile karşılaştırıyor. Önceki karşılaştırma (`path == toplevel`)
  worktree içinde her zaman doğruydu; kapı hiç yeşile dönmüyor, her leaf
  degrade kaydıyla ilerliyordu (#108).
- **Regresyon testi** — worktree içinden `check()` ok döner, ana dizinden hata
  verir; mutasyonla doğrulandı.
- **`main_root()` sertleştirildi** — ana çalışma dizini `git worktree list
  --porcelain` ilk satırından okunur. Submodule ve `--separate-git-dir`
  düzenlerinde git ortak git dizinini bildirir; kapı bu durumda da kapalı
  yönde davranır (ana çalışma dizininden commit engellenir).
- **Gerçek git düzeni testi** — `git init` + `git worktree add` ile kurulan
  depoda `main_root` ve `check()` doğrulanır.
- Degrade worktree dalındaki karşılaştırma bilinçli olarak değişmedi.

## 2.34.0 — 2026-11-01

- **Refactor leaf türü** — `entry.kind: refactor`; yol `pure_technical`.
  Refactor artık yasak değil, ayrı ve kanıtlı bir iş.
- **Davranış değişmedi kanıtı** — `verification.refactor`: `baseline`/`after`
  commit + tests, `unchanged: true`, `files_changed`, UI için `ui_unchanged` ve
  eşit snapshot hash'i. Baseline, after'ın atası olmak zorunda.
- **Zorunlu architect gate'i** — refactor seal'inde her CP `gates.architect:
  true` ister; `leaf-done` anında `verification.refactor` yoksa geçmez.
- **Boyut sınırı** — 10 dosyaya kadar normal, 11–20 uyarı, 20 üstü hata.
- **Tetik politikası** — `delivery/policies/refactor-triggers.md`: dosya/tip
  boyutu, yayılma, tekrar eden hata, epic kapanışı, test edilemez bağımlılık,
  büyük feature öncesi. Tetik yoksa leaf açılmaz.
- **Architect playbook** — `agents/architect/variants/refactor.md`: survey →
  propose → refactor → record, deletion test, `Strong/Worth exploring/Speculative`.
- **Epic closure** — borç check-in adımı zorunlu; `Strong` bulgu leaf açar,
  ertelenen her bulgu gerekçesiyle raporda görünür.

## 2.33.0 — 2026-11-01

- **AC denetim türü** — `tests_plan.cases[].check`: `gate` | `unit` | `snap` |
  `manual` | `doc`. Her kabul kriterinin hangi mekanizmayla doğrulandığı yazılı
  hale geldi.
- **`package_version: 4`** — yeni leaf'lerde `check` zorunlu. v2/v3 seal'ler
  değişmeden geçer; kural yalnız v4'e uygulanır.
- **Gate eşleşmesi** — `snap` türü case, checkpoint'te `gates.ui: true`;
  `manual` türü case `gates.human: true` olmadan mühürlenemez. Görsel veya
  insan doğrulaması isteyen AC artık ilgili gate olmadan geçemez.
- **İnsan kapısı kanıtı** — `package_version: 4` leaf'te `gates.human: true`
  olan her CP `leaf-done` anında `reviews.human: approved` ister; düşük riskte
  bile açık insan kapısı kendiliğinden kapanmaz.
- **Skill'ler** — `test-plan` beş türü ve seçim kuralını, `work-package`
  şablonu v4'ü ve `check` alanını anlatıyor.

## 2.32.1 — 2026-11-01

- **CI: commit görünürlüğü** — `evidence.verify()` commit'i yerelde bulamazsa
  `origin`'den fetch eder ve `diff_hash` kontrolünü korur. Epic branch'i
  birleşmeden kapandığı için commit `main`'de yoktu; `issue-doctor` kırmızıya
  düşüyordu. Protokol artık leaf kapanışından önce `git push -u origin epic-<E>`
  istiyor. Uzakta da bulunmayan commit reddedilir.
- **Regresyon testleri** — sahte origin'den fetch, uzakta olmayan commit,
  repo yokken fetch atlama ve fetch sonrası `diff_hash` eşleşmesi test edilir.

## 2.32.0 — 2026-11-01

- **Skill yazım sözleşmesi** — `delivery/policies/skill-writing.md`: description
  bir context pointer (ne + `Use when` tetikleyicisi), her adım checkable koşulla
  biter, her skill `## Done when` ile biter, ayrıntı kardeş dosyaya taşınır.
- **Skill lint** — `doctor.check_skills()` artık description varlığını ve
  uzunluğunu, tetikleyici ifadesini, `## Done when` bölümünü ve göreli
  markdown linklerini denetler; 300 satır üstü hata, 200 üstü uyarı verir.
  Negatif ve pozitif testler `delivery/tests/test_skills.py`.
- **Dokuz runtime skill uyarlandı** — description'lar tetikleyici kazandı,
  her skill `## Done when` ile kapatıldı. Skill seçimi artık ölçülebilir.

## 2.31.2 — 2026-11-01

- **Kurulu skill kopyası denetimi** — `install.sh` becerileri `.agents/skills/`
  altına kopyalar; kopya `skills/` kaynağından farklıysa `doctor` uyarır. Bayat
  kopya sessizce eski kural (ör. `package_version: 2` seal) öğretmesin.
- **Kurulum çıktısı artık ignore** — `.agents/`, `.claude/` ve `skills-lock.json`
  git'e girmez; makineye özel ve kaynaktan türetilir.

## 2.31.1 — 2026-11-01

- **Proje exclude'ları seal kontrolünde geçerli** — `doctor` risk tabanını ve
  capability gap hesabını `.kit/capabilities.yaml` `exclude` listesine göre
  yapar. Önceki davranışta exclude yalnız `resolver`/`brief` tarafında
  uygulanıyor, seal kontrolünde sıfırlanıyordu; bu yüzden proje bir domain
  capability'sini hariç tutsa bile metin eşleşmesi risk tabanını yükseltip
  leaf'i mühürlenemez hale getiriyordu.
- **Kanıt geçerliliği korunur** — evidence rol denetimi (`allowed_agents`)
  exclude'suz çözümden gelmeye devam eder; proje seviyesinde exclude eklemek
  geçmiş `leaf-done` kanıtlarını geçersiz kılmaz.
- **Sessiz risk indirimi yok** — exclude bir capability'yi susturduğunda ve o
  capability'nin risk tabanı seal riskinin üstündeyse doctor `capability
  exclude:` uyarısı basar; karar görünür kalır.
- **Kit pin'i yayınlanmış olmalı** — `doctor --product` artık kit submodule
  pininin `origin/main`in atası olduğunu doğrular. VERSION dizesi aynı olsa da
  merge edilmemiş bir branch commit'ine bağlanmak hata verir; `origin/main`
  ref'i yoksa (çevrimdışı/eksik klon) uyarı basar. Yalnız `.git` içeren
  submodule/kurulumlarda çalışır; `vendor_sync` kopyaları etkilenmez.
- **Ham worktree yakalanır** — `doctor` linked worktree'nin Orca'da kayıtlı
  olduğunu doğrular; `git worktree add` ile açılan checkout hata verir. Orca
  yoksa sessizce degrade olur, CI'da atlanır. `CONTRACT.md` I17/I18 olarak
  kurala bağlandı.

## 2.31.0 — 2026-10-31

- **Orca capability detection** — `orca_capabilities.py` reads
  `orca agent-context` and caches the command/flag schema under
  `.orchestration/`. Product projects no longer compare Orca versions; missing
  features degrade with a recorded reason. Kit self-development adapts to new
  Orca releases. `compat.py` names the 66 commands/flags the kit relies on for
  maintainer CI.
- **Orca-native orchestration** — `orca_wave` resumes the epic Run with
  `run-use`, creates one Task per CP with `task-create --deps`, starts workers
  with `worker-start --task`, updates Tasks on settlement, and supports
  `--model/--effort`.
- **Gates and messages** — `orca_gate.py` adds `ask/reply/inbox/send` and
  `gate-create/gate-resolve/gate-list`; human decisions use Orca gates plus
  GitHub `human-qa`.
- **Live checkpoints** — `update.py` mirrors progress to
  `worktree set --comment --workspace-status`; `transition.py` syncs state,
  unread/read and gate resolution. GitHub remains the durable ledger.
- **Worktree metadata** — `epic_worktree.py` links the epic issue/reference,
  sets metadata, exposes `worktree ps`, repo base ref and reference helpers.
- **Report** — includes live Orca worktree/run/task/worker/gate state and
  optional session-search links.
- **Browser/native evidence** — `ui-gate` uses typed Orca browser commands
  (snapshot/click/fill, console/network, screenshot/PDF, device/profile/ports);
  `platform-gate` uses `orca computer` and `orca emulator` with artifact links.
- **Automation templates** — `automations.py` plus disabled-by-default
  stale-lease, weekly doctor, PR queue and weekly report jobs.
- **Worktree speed** — `init` generates `orca.yaml` `sharedDirectories` and
  `.worktreeinclude` for gitignored local files.

## 2.30.0 — 2026-10-31

- **Epic worktree** — bir epic = tek worktree + tek branch + tek PR. Yeni
  `epic_worktree.py` (`ensure`/`check`/`sync`/`remove`/`prune`) ilk leaf claim'inde
  `epic-<N>` worktree'sini bir kez açar; leaf'ler aynı checkout'u kullanır.
  Rebase yasak, yeni leaf öncesi `origin/main` merge edilir.
- **Orca sert kapısı** — `orca_gate.py` Orca'yı ölçer; worktree/run/task yoksa
  `guard.sh` kaynak commit'ini engeller. Degrade yalnız `--degrade --reason` ile
  issue'ya `run degrade:` yazılarak mümkün; evidence'ta `degrade` bloğu aranır.
- **Native subagent yerine worker** — `AGENTS.md`'ye otomatik `demir-kit:delivery`
  bloğu enjekte edilir (`delivery_block.py`, `init`/`adopt`); agent ürün reposunda
  doğru komutları görür. `next-leaf --claim` sıradaki üç Orca komutunu yazar.
- **Kanıt şeması** — `worktree`, `degrade`, `verification.local_gate` eklendi.
  `package_version: 3` yeni leaf'lerde worktree + worker/degrade zorunlu.
- **CI eşiği** — `critical` CI `success` ister; `high` yerel kapı
  (`local_gate`, exit 0) ile kapanabilir. Kapanışta sürpriz CI hatası bitirildi.
- **Kapanış** — `transition --to epic-done` merge edilmiş PR + temiz worktree
  doğrular, worktree'yi siler (`--keep-worktree`); `--report` özet yayınlar.
  `update.py --approval yes` artık `--ask` zorunlu kılar.
- **Rapor** — commit evidence'tan, reviewer'lar rol bazında sayılır, süre
  claim→son evidence; worktree/degrade satırları eklenir.
- **PR akışı** — leaf PR'ları kaldırıldı; tek epic PR `epic-<E>` → `main`.

## 2.29.1 — 2026-10-30

- **CHANGELOG↔VERSION drift kontrolü** — `doctor.check_version_drift` artık
  CHANGELOG'un ilk sürüm başlığını da VERSION ile karşılaştırır; kit kendi
  içinde sürüm drift'i üretemez (CI gate'i bunu yakalar). Eksik sürüm
  başlığında uyarır. Test eklendi.

## 2.29.0 — 2026-10-30

- **hig-audit skill** — Apple tasarım denetimi (iOS/iPadOS/macOS, SwiftUI
  öncelikli): sistematik repo keşfi, canlı HIG referanslı non-negotiable'lar
  (Liquid Glass functional-layer kuralı + slider/toggle istisnası ve
  "sparingly" uyarısı dahil), `HIG-*` bulguları (severity `critical|high|medium`,
  `Dosya:Satır`, `hig_ref`, somut fix), Türkçe rapor şablonu; opsiyonel Apple
  Design Awards + anti-slop lens (`--awards`). Hedef platform dönemi projeden
  türetilir; OS hardcode yok.
- **apple-hig pack** — checklist non-negotiable evidence maddeleriyle
  genişletildi: touch target 44pt, kontrast 4.5:1/3:1, Dynamic Type, Liquid
  Glass katman kuralı + istisna, SF Symbols, contextual permission, alert
  disiplini.
- **apple-a11y pack** — derin tarama maddeleri: label+trait+hint, Dynamic
  Type, sayısal kontrast, Differentiate Without Color, Reduce Motion,
  Keyboard/Switch Control, touch target.
- **Registry/policy** — `skills.runtime` += `hig-audit`;
  `quality-gates.md` platform gate'te Apple pack'leri için prosedür referansı.

## 2.28.1 — 2026-10-30

- **Güncellik denetimi** — `doctor --product`, `kit.config.yaml kit.version` ile
  vendored/submodule kit `VERSION`'ını karşılaştırır; drift varsa iki modun
  da güncelleme komutuyla birlikte uyarır.
- **Submodule güvenliği** — `vendor_sync --apply` hedef kit dizininde `.git`
  görürse reddeder (`git submodule update --remote` önerir); yanlışlıkla
  submodule checkout'unun üzerine yazamaz.
- **Vendor kopya temizliği** — vendor kopyaya kitin `.gitignore`'ı da kopyalanır;
  scriptlerin ürettiği `__pycache__` ürün reposunda kirletmez.
- **Doküman** — `runbooks/adaptation.md` "Kit güncelleme": submodule ve vendor
  kopya modlarının güncelleme komutları, karıştırma uyarısı.
- **Test** — sürüm drifti, submodule reddi, .gitignore kopyası senaryoları;
  378 test.

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
