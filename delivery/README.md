# Delivery — v2.25

Epic → leaf → kanıt → closure → epic kabulü. Tek runtime `delivery/`;
arşiv `archive/v1.7/` yalnız referans içindir.

| Dosya | Ne |
|-------|-----|
| [CONTRACT.md](CONTRACT.md) | Durum makinesi, geçişler, risk modeli, DoD |
| [FLOW.md](FLOW.md) | Diyagram + etiket özeti |
| [registry.yaml](registry.yaml) | Path, agent, risk glob, etiket kaynağı |
| [protocol/](protocol/execution.md) | Kuyruk, claim, resume, seal, health, evidence |
| [policies/](policies/approval.md) | Onay, path, kalite, eskalasyon, human-qa |
| [runbooks/](runbooks/epic-intake.md) | Intake, closure, PR ve adaptasyon |
| [schemas/](schemas/leaf.schema.json) | Epic, leaf, evidence, closure şemaları |
| [scripts/](scripts/doctor.sh) | doctor, guard, next-leaf, transition, evidence, install |
| `agents/`, `capabilities/`, `templates/`, `profiles/`, `packs/` | Roller, yetenek matrisi ve kaynaklar |

## Komutlar

```bash
./delivery/scripts/doctor.sh            # sözleşme denetimi
./delivery/scripts/doctor.sh --issue 12 # seal + evidence
./delivery/scripts/next-leaf.sh --claim # sıradaki leaf + lease
./delivery/scripts/next-leaf.sh --release --issue N # bayat lease bırak
./delivery/scripts/transition.sh --issue N --to leaf-done # tek yazıcı geçiş
./delivery/scripts/capabilities.py --matrix      # rol × yetenek matrisi
./delivery/scripts/capabilities.py --validate    # referans bütünlüğü
./delivery/scripts/variants.py --role designer    # variant eşleşmesi
./delivery/scripts/resolver.py --surface web.app --platform web --stack next
./delivery/scripts/detect.py --project . --json   # read-only fingerprint
./delivery/scripts/profiles.py --project .        # profile composition
./delivery/scripts/standards.py --project .        # project standards
./delivery/scripts/verify.py --project .          # read-only adaptation check
./delivery/scripts/adopt.py --project . --apply   # one-command SDLC injection
./delivery/scripts/init.py --project . --apply      # project wiring
./delivery/scripts/adapt.py --add platform.android # capability diff / --apply
./delivery/scripts/protect_main.sh --apply   # main PR + required check
./delivery/scripts/eval.py --check              # eval scenario enforcement
./delivery/scripts/guard.sh --issue 12  # G1 + risk
./delivery/scripts/vendor_sync.sh --target ../Product --check
./delivery/scripts/vendor_sync.sh --target ../Product --apply
./install.sh --with-platform            # Orca skill kurulumu
```

## Otonomi sınırı

`low` / `medium` leaf otomatik kapanır. İnsan yalnız risk `high`/`critical`
leaf, geri dönülemez işlem, bütçe aşımı ve epic kabulünde devreye girer
([policies/approval.md](policies/approval.md)).
