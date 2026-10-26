# How

1. Oku: leaf seal, [CONTRACT](../../CONTRACT.md), [quality-gates](../../policies/quality-gates.md).
2. Yalnız worktree/issue kapsamında değişiklik; `guard.sh --issue N`.
3. Her CP: testi önce yaz (red), sonra uygula (green).
4. Gate: `doctor.sh --issue N --checkpoint CP-x` exit 0.
5. Evidence yaz ([evidence](../../protocol/evidence.md)); tester'a bildir.
