# Seal protocol

Leaf'i yürütülebilir hale getirme. Şema: [leaf.schema.json](../schemas/leaf.schema.json).
Durum geçişi: `scope-confirmed` → `agent-approved` (T2).

Yeni leaf'ler `package_version: 2` ile mühürlenir; bu, evidence v3
(`verification`) zorunluluğunu getirir. `1` yalnız eski kayıtlar içindir.

## Girdi kontrolü

1. Issue bir **leaf**; scope-only epic değil.
2. Parent epic `scope-confirmed`.
3. Her KEEP maddesi bir child issue'ya bağlı.
4. AC'ler test edilebilir; `out_of_scope` dolu.

## Adımlar

1. Issue body'deki `demir-kit` YAML bloğunu `leaf.schema.json`'a göre doldur.
2. Her `AC-n` için en az bir `tests_plan` case'i (`T-n`, `ac: AC-n`) yaz.
3. Her CP için `gates.behavior: true`; risk seviyesini `registry.yaml risk` ile belirle.
4. `dependencies` içine bloklayan issue'ları yaz (`kind: blocks`).
5. Doğrula:

```bash
./delivery/scripts/doctor.sh --body /tmp/leaf.md
```

6. Issue body'yi güncelle ve `agent-approved` ekle.
7. Sıradaki adım: [health-check.md](health-check.md).

## Örnek

```yaml demir-kit
demir_kit_version: "2"
package_version: 2
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
      - { id: T-1, ac: AC-1, text: blocked dependency leaf'i kuyruktan düşer }
      - { id: T-2, ac: AC-1, text: en eski uygun leaf seçilir }
  - checkpoint_id: CP-2
    cases:
      - { id: T-3, ac: AC-2, text: pass CP evidence ile atlanır }
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
