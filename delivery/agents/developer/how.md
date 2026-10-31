# How

1. Oku: leaf seal, [CONTRACT](../../CONTRACT.md), [quality-gates](../../policies/quality-gates.md).
2. Yalnız epic worktree/issue kapsamında değişiklik; `guard.sh --issue N`.
   Ana checkout'tan kaynak commit'i yapılmaz; epic worktree'si `next-leaf --claim`
   tarafından bulunur/açılır.
3. Her CP: testi önce yaz (red), sonra uygula (green).
4. Gate: `doctor.sh --issue N --checkpoint CP-x` exit 0.
5. Evidence yaz ([evidence](../../protocol/evidence.md)); tester'a bildir.

## Contract
- **Input:** sealed leaf, `tests_plan`, reference.
- **Output:** code + behavior evidence.
- **Done when:** gate exit 0; scope respected.
- **Forbidden:** scope expansion, self-approval.
- **Handoff:** tester.
