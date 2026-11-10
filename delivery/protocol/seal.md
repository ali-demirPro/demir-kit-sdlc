# Seal protocol

Leaf'i yürütülebilir hale getirme. Şema: [leaf.schema.json](../schemas/leaf.schema.json).
Durum geçişi: `intake` / `scope-confirmed` → `agent-approved` (T2; parent epic `scope-confirmed`).

Yeni leaf'ler `package_version: 4` ile mühürlenir. Bu sürüm önceki
zorunlulukları devralır ve her `tests_plan` case'inde `check` alanı ister:
`gate` | `unit` | `snap` | `manual` | `doc`. `snap`, checkpoint'te
`gates.ui: true`; `manual`, `gates.human: true` gerektirir. `3`, `2` ve `1`
yalnız eski kayıtlar içindir; onlarda `check` varsa eşleşme yine denetlenir.

## Girdi kontrolü

1. Issue bir **leaf**; scope-only epic değil.
2. Parent epic `scope-confirmed`.
3. Her KEEP maddesi bir child issue'ya bağlı.
4. AC'ler test edilebilir; `out_of_scope` dolu.
5. Proje öncelikleri okunur (`kit.config.yaml product.priorities` +
   [project-priorities.md](../policies/project-priorities.md)); design system
   ve mimari dokümanlar `reference.paths`'ta gösterilir.

## Adımlar

1. Issue body'deki `demir-kit` YAML bloğunu `leaf.schema.json`'a göre doldur.
2. Her `AC-n` için en az bir `tests_plan` case'i (`T-n`, `ac: AC-n`) yaz;
   `package_version: 4` ise her case'te `check` alanını doldur.
3. Her CP için `gates.behavior: true`; risk seviyesini `registry.yaml risk` ile belirle.
4. `dependencies` içine bloklayan issue'ları yaz (`kind: blocks`).
5. Doğrula:

```bash
./delivery/scripts/doctor.sh --body /tmp/leaf.md
```

`doctor` seal lint uyarılarını da yazar: belirsiz AC metni, çalıştırılabilir iz
taşımayan unit/gate case'i, tekrarlı ID veya bilinmeyen AC/CP. Uyarılar
`--strict` ile hata olur.

6. Issue body'yi güncelle; insan `demir-kit-accept` yorumuyla `agent-approved` ekle:

```yaml demir-kit-accept
issue: 260
by: <login>
decision: accepted
binding_sha256: sha256:<64 hex>
binding_base: <onay anındaki HEAD sha>
```

`binding_sha256` seal bloğu + taban commit'in kanonik digest'idir:

```bash
BASE="$(git rev-parse HEAD)"
python3 delivery/scripts/approvals.py digest --body-file /tmp/leaf.md --base "$BASE"
```

`binding_base` alanına tam 40 karakter sha yaz; kısa sha de kabul edilir ve
digest üretilirken/doğrulanırken `git rev-parse` ile tam sha'ya çözülür.
Çözülemeyen taban commit digest üretmez ve onayı geçersiz sayar. Kısa sha'nın
ham metni üzerinden üretilmiş eski digest'ler geriye dönük geçerlidir.

Onaydan sonra seal gövdesi değişirse ya da taban commit HEAD'in atası değilse
`doctor --issue` hata verir; `guard.sh --issue` kaynak yazımını reddeder. Alanı
taşımayan eski kayıtlar geriye dönük geçerlidir.

7. Sıradaki adım: [health-check.md](health-check.md).

## Örnek

```yaml demir-kit
demir_kit_version: "2"
package_version: 4
mode: extend
epic: 10
entry:
  kind: chore
factory:
  profile: kit-internal
intent: Execution protokolünü ve kuyruk seçimini v2 runtime'a taşımak.
surfaces: [kit.docs]
reference:
  kind: github_paths
  summary: CONTRACT.md ve mevcut runbook'lar referans.
  paths: [delivery/CONTRACT.md, delivery/protocol/execution.md]
acceptance_criteria:
  - id: AC-1
    text: Kuyruk seçimi bağımlılık ve etiketlere göre deterministik çalışır.
  - id: AC-2
    text: Resume, tamamlanmış CP'yi yeniden koşmadan devam eder.
out_of_scope:
  - Orca sürüm yükseltmesi
risk:
  level: medium
  reasons: [routing logic]
tests_plan:
  - checkpoint_id: CP-1
    cases:
      - { id: T-1, ac: AC-1, text: blocked dependency leaf'i kuyruktan düşer, check: unit }
      - { id: T-2, ac: AC-1, text: en eski uygun leaf seçilir, check: unit }
  - checkpoint_id: CP-2
    cases:
      - { id: T-3, ac: AC-2, text: pass CP evidence ile atlanır, check: gate }
checkpoints:
  - id: CP-1
    title: Queue and claim
    gates: { behavior: true, architect: false, commercial: false, ui: false, human: false }
  - id: CP-2
    title: Resume algorithm
    depends_on: [CP-1]
    gates: { behavior: true, architect: false, commercial: false, ui: false, human: false }
```

## Sık hatalar

| Hata | Sonuç |
|------|-------|
| AC'yi test case'siz bırakmak | `doctor` fail; seal yok |
| `behavior: false` | şema fail |
| Risk seviyesini düşük yazmak | `guard.sh` glob ile yükseltir |
| Parent epic'i mühürlemek | contract ihlali (T2 leaf ister) |
| `tests_plan` CP'sini atlamak | `doctor` fail |
