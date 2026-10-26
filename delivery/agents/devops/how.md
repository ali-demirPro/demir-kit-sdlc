# How

1. Behavior gate komutunu doğrula/güncelle.
2. Pipeline kırıldıysa blocker.
3. Rollout/channel devops adımı (non-store).

## Contract
- **Input:** `ecosystem.yaml`, CI, deploy target.
- **Output:** runnable gate commands, pipeline/rollout.
- **Done when:** health-check and pipeline green.
- **Forbidden:** prod/store action without human.
- **Handoff:** orchestrator.
