# Headless davranış doğrulama

demir-kit davranış kapısı, mümkün olduğunca **simülatör/tarayıcı olmadan** doğrulama yapmayı önerir: domain mantığı UI’dan ayrılır, gate komutu ms–sn ölçeğinde tekrarlanabilir.

## Principles

1. **Domain logic decoupled from UI** where possible (Flutter: pure Dart module; web: shared package).
2. **Gate command** in `ecosystem.yaml` should prefer headless tests/CLI over emulator when validating behavior.
3. **Integration tests** describe user-visible outcomes; unit tests alone are insufficient for UI-heavy CPs.

## Surface configuration

```yaml
surfaces:
  game.client:
    gates:
      behavior: "./scripts/gate-behavior.sh {checkpoint}"
      behavior_mode: headless   # headless | unit-only | emulator-required
    behavior_cli:
      description: "Optional: dart run tool/agent_cli.dart --checkpoint {checkpoint}"
```

## Checkpoint mapping

| CP type | Preferred proof |
|---------|-----------------|
| Domain rules | Unit + headless CLI |
| API / repository | Integration test, no browser |
| UI | Behavior smoke where possible; full UI in `ui-gate` |

## Coordinator

- Run `health-check` to ensure gate script exists.
- `behavior-gate` skill: red-green on tests tied to `tests_plan` in issue YAML.

## Multi-stack note

Document `behavior_mode: emulator-required` when headless is not yet available; accept slower loops until `behavior_cli` exists.
