# Delivery — v2.2

Epic → leaf → kanıt → closure → epic kabulü. Tek runtime `delivery/`;
arşiv `old/` yalnız referans içindir.

| Dosya | Ne |
|-------|-----|
| [CONTRACT.md](CONTRACT.md) | Durum makinesi, geçişler, risk modeli, DoD |
| [FLOW.md](FLOW.md) | Diyagram + etiket özeti |
| [registry.yaml](registry.yaml) | Path, agent, risk glob, etiket kaynağı |
| [protocol/](protocol/execution.md) | Kuyruk, claim, resume, seal, health, evidence |
| [policies/](policies/approval.md) | Onay, path, kalite, eskalasyon, human-qa |
| [runbooks/](runbooks/epic-intake.md) | Intake ve closure |
| [schemas/](schemas/leaf.schema.json) | Epic, leaf, evidence, closure şemaları |
| [scripts/](scripts/doctor.sh) | doctor, guard, next-leaf, install |
| `agents/`, `templates/`, `profiles/`, `packs/` | Roller ve kaynaklar |

## Komutlar

```bash
./delivery/scripts/doctor.sh            # sözleşme denetimi
./delivery/scripts/doctor.sh --issue 12 # seal + evidence
./delivery/scripts/next-leaf.sh --claim # sıradaki leaf
./delivery/scripts/guard.sh --issue 12  # G1 + risk
./install.sh --with-platform            # Orca skill kurulumu
```

## Otonomi sınırı

`low` / `medium` leaf otomatik kapanır. İnsan yalnız risk `high`/`critical`
leaf, geri dönülemez işlem, bütçe aşımı ve epic kabulünde devreye girer
([policies/approval.md](policies/approval.md)).
