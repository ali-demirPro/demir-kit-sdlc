# How

1. Event + flag gereksinimini issue'ya yaz.
2. Rollout % ve guardrail metrikleri.
3. Sonuç özeti + öneri (partial rollout, next test).

## Contract
- **Input:** feature flag, analytics instrumentation.
- **Output:** rollout %, guardrail readout, next-test recommendation.
- **Done when:** metric result + recommendation posted.
- **Forbidden:** shipping without flag/guardrail.
- **Handoff:** discovery `growth/plan`, orchestrator.
