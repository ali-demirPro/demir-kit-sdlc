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

### B6 — Root çözümleme (git ortak kökü)

- **Girebilir:** `git rev-parse --git-common-dir` ile bulunan ortak kök; ortak
  kökte `kit.config.yaml` varsa kökü orası çözer (örn. `cycle.py project_root`,
  `guard.sh` `PRODUCT_ROOT`); aksi halde mevcut checkout.
- **Giremez:** Worktree'ye özgü kök yerine ana checkout varsayımı olmadan durum
  yazımı — `.kit/` çıktıları ortak köke ait olmalıdır; worktree'ye yazılan durum
  kopyası bozuk sayılır.
- **Not:** Bu tarif D-1 (#373) kitlib **tek `project_root` sözleşmesi**nin kapsamına
  işaret eder; bugün scriptler arasında birden çok tanım vardır ve kitlib bunları
  tek sözleşmede birleştirir. Bu dosya o kararı vermez, çelişmez, yalnız bugünkü
  davranışı ve hedef yönü tarif eder. Detay ve migrasyon D-1'dedir.
- **Denetim:** `doctor.sh` + `delivery/tests/` (worktree fixture'ları) + D-1 testleri.

### B7 — Kapsam taşması yok (guard + transition)

- **Girebilir:** Yalnız seal yüzeyindeki (`surfaces`) glob'ların kapsadığı dosyalar;
  epic kapsamı dışına sessiz taşma yasaktır.
- **Giremez:** Başka epic'in kapsamı, kit genelinde "gerekirse" değişiklikler;
  kapsam dışı ihtiyaç = yeni leaf/issue, sessiz genişleme değil.
- **Denetim:** `./delivery/scripts/guard.sh --issue N` (G1 capability dışı yazım
  reddi + risk eskalasyonu) + `transition.sh --issue N` (tek yazıcı geçişleri) +
  `gate.sh --issue N --checkpoint CP-x`.

## Audit paths (module × check)

| Modül | doctor | unittest | registry | guard |
|-------|--------|----------|----------|-------|
| `delivery/CONTRACT.md` | ✔ (version/contract) | ✔ | — | — |
| `delivery/registry.yaml` | ✔ | ✔ | ✔ (tek kaynak) | — |
| `delivery/schemas/` | ✔ (`--body`/`--issue`) | ✔ | ✔ (şema referansları) | — |
| `delivery/policies/` | ✔ (link + tutarlılık) | ✔ | ✔ (quality-gates referansı) | — |
| `delivery/protocol/` | ✔ (link kontrolü) | ✔ | ✔ (protocol referansları) | — |
| `delivery/agents/` | ✔ (varyant + agent.yaml) | ✔ | ✔ (agent_variants) | — |
| `delivery/scripts/` | ✔ | ✔ | ✔ (script yolları) | ✔ (G1 + risk) |
| `delivery/tests/` | ✔ | ✔ | — | — |
| `skills/` | ✔ (skill denetimi) | ✔ | ✔ (`skills.runtime`) | — |
| `.agents/skills/` | ✔ (kopya denetimi) | — | ✔ (kaynak `skills/`) | — |
| `discovery/` | ✔ (link/ağ) | — | — | ✔ (kapsam) |
| `archive/v1.7/` | ✔ (legacy) | ✔ | — | — |
| `docs/` | — (kapsam dışı; link hedefi geçerli olmalı) | — | — | ✔ (kapsam) |
| `ecosystem.yaml` / `kit.config.yaml` | ✔ (wiring/version) | ✔ | ✔ | ✔ (`PRODUCT_ROOT`) |

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
