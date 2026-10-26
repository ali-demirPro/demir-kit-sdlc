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
  comparison_valid: false
  platform: skipped
  adversarial: { reviewer_a: approved, reviewer_b: approved }
  risk: medium
tests:
  - { case: T-1, result: pass, note: doküman kontrolü }
findings: []
notes: Kısa Türkçe özet.
status: pass
```
````

## Kurallar

- `status: pass` için behavior `exit_code: 0` ve tüm testler `pass` olmalı (şema zorlar).
- `agent`: CP'yi üreten rol (`developer`, `tester`, …). Yeni evidence'larda zorunlu;
  eski kayıtlarda yoksa doctor uyarı verir.
- Risk seviyesinin istediği reviewer alanları dolu olmalı; atlanan gate `skipped` yazar.
- Açık bulgu (`findings[].status: open`) varsa `status: pass` olamaz.
- Comment issue'ya `gh issue comment <N> --body-file` ile yazılır.
- Screenshot/artifact varsa link `notes` alanına eklenir.
- Aynı CP için ikinci evidence yazılmaz; düzeltme gerekiyorsa ilk blok `status: fail`
  kalır, yeni blok eklenir (geçmiş korunur).

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
