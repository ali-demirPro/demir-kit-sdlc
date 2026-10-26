# How

1. Epic + children oku; zorunlu label eksikse düzelt, yoksa devam.
2. `path_id` seç (`registry.yaml` paths + signals).
3. `active_agents` / `inactive` + gerekçe yaz (epic comment).
4. Architect + analist planı; onay = issue truth.
5. Kuyruk: `next-leaf --claim`; health-check `ready` → `executing`.
6. Her CP: behavior → review → evidence; bütçe aşımı → blocker.
7. Leaf kapanışı: risk `low`/`medium` otomatik, `high`/`critical` insan QA.
8. Tüm leaf'ler → [epic-closure](../runbooks/epic-closure.md) (otomatik).
9. Closure `pass` → epic insan kabulü → `epic-done`.
10. Blocker → [escalation](../policies/escalation.md); follow-up issue.
11. Closure metriklerini [metrics](../metrics/README.md) ile yaz.

Policies: [delivery/policies/](../policies/approval.md) · Sözleşme:
[CONTRACT.md](../CONTRACT.md).
