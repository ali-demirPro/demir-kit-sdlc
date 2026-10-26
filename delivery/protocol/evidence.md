# Evidence protocol

Her CP için tek kanıt comment'i. `leaf-done` bu bloklar olmadan imkânsızdır.
Şema: [evidence.schema.json](../schemas/evidence.schema.json).

## Şablon

````markdown
```yaml
demir-kit-evidence
demir_kit_version: "2"
cp_id: CP-1
issue: 12
agent: developer
commit: abc1234
behavior:
  command: ./delivery/scripts/doctor.sh --checkpoint CP-1
  exit_code: 0
  checkpoint: CP-1
reviews:
  architect: skipped
  commercial: skipped
  ui: skipped
  ui_visual: skipped
  ui_interaction: skipped
  comparison_valid: false
  platform: skipped
  human: skipped
  human_second: skipped
  adversarial: { reviewer_a: approved, reviewer_b: approved }
  risk: medium
verification:
  commit: abc1234
  diff_hash: "sha256:<64 hex>"
  ci:
    status: success
    run_id: "123456"
    url: https://github.com/owner/repo/actions/runs/123456
  reviewers:
    - role: adversarial
      id: ses_reviewer
      model: provider/model
      prompt_hash: "sha256:<64 hex>"
      diff_hash: "sha256:<64 hex>"
worker:
  run_id: run_…
  task_id: task_…
  dispatch_id: ctx_…
  agent: opencode2
  outcome: succeeded
tests:
  - { case: T-1, result: pass, note: doküman kontrolü }
findings: []
notes: Kısa Türkçe özet.
status: pass
```
````

Paralel wave'lerde aynı alanları `workers:` listesi olarak yaz:

```yaml
workers:
  - { run_id: run_…, task_id: task_…, dispatch_id: ctx_…, agent: opencode2, outcome: succeeded }
  - { run_id: run_…, task_id: task_…, dispatch_id: ctx_…, agent: opencode2, outcome: succeeded }
```

## Kurallar

- `status: pass` için behavior `exit_code: 0` ve tüm testler `pass` olmalı (şema zorlar).
- `agent`: CP'yi üreten rol (`developer`, `tester`, …). Yeni evidence'larda zorunlu;
  eski kayıtlarda yoksa doctor uyarı verir.
- Risk seviyesinin istediği reviewer alanları dolu olmalı; atlanan gate `skipped` yazar.
- `high` leaf'te `reviews.human: approved`; `critical` leaf'te ayrıca
  `reviews.human_second: approved` zorunludur. İnsan onayı olmadan `leaf-done` geçmez.
- `gates.ui` açıksa `ui_visual`, `ui_interaction` ve `comparison_valid: true` birlikte
  aranır; tek `ui: pass` yeterli değildir.
- `gates.commercial` açıksa veya risk `critical` ise `reviews.commercial: approved`
  zorunludur.
- `package_version: 2` leaf'lerde `verification` zorunludur: commit SHA, diff hash,
  CI sonucu ve reviewer kimliği. Eski `package_version: 1` kayıtları geçerlidir.
- `verification.commit` git'te bulunmalı; `diff_hash` o commit'in binary diff'iyle
  eşleşmeli. CI `success` ise run aynı commit'te ve başarılı olmalı; `high`/`critical`
  için CI `skipped` kabul edilmez.
- Her reviewer `id`, `model`, `prompt_hash` ve `diff_hash` taşır; ID'ler benzersiz,
  uygulayıcıdan farklı ve inceledikleri diff aynı olmalı.
- Açık bulgu (`findings[].status: open`) varsa `status: pass` olamaz.
- Comment issue'ya `gh issue comment <N> --body-file` ile yazılır.
- Screenshot/artifact varsa link `notes` alanına eklenir.
- Aynı CP için ikinci evidence yazılmaz; düzeltme gerekiyorsa ilk blok `status: fail`
  kalır, yeni blok eklenir (geçmiş korunur).

## Verification üretme

```bash
python3 delivery/scripts/evidence.py --commit HEAD \
  --ci-run 123456 \
  --reviewer '{"role":"adversarial","id":"ses_x","model":"provider/model","prompt_hash":"sha256:..."}'
```

`--ci-run` yerine `--ci-skipped "sebep"` kullanılabilir; `high`/`critical` için
CI zorunludur.

## Denetim

```bash
./delivery/scripts/doctor.sh --issue <N> --checkpoint CP-1
```

- `leaf-done` varsa her CP için `status: pass` evidence arar.
- `epic-done` varsa `demir-kit-closure` bloğu arar.

## Kötü örnekler

| Örnek | Neden |
|-------|-------|
| "Testler geçti" (blok yok) | makine doğrulayamaz |
| `exit_code: 0` ama test `fail` | şema reddeder |
| Reviewer alanı boş | risk gate'i kanıtsız |
| Aynı CP'ye iki `pass` | geçmiş izlenemez |
