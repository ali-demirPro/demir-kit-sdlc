# Quality attributes

| Attribute | Target | How measured | Owner surface |
|-----------|--------|--------------|---------------|
| **Stability** | No P0 crashes in primary flow | Crash-free sessions / release | … |
| **Reliability** | Critical actions succeed ≥ 99.5% | Synthetic + client metrics | … |
| **Consistency** | Same business rules on all clients | Shared domain tests / contract tests | … |
| **Availability** | … | … | … |
| **Latency** | p95 &lt; … ms | … | … |

## Consistency rules

- Idempotency keys: …
- Time zone / locale: …
- Offline behavior: …

## Release / rollback

- …
