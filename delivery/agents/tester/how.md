# How

1. `tests_plan` case'lerini koş; her CP için
   `doctor.sh --issue N --checkpoint CP-x`.
2. Fail → developer'a geri; pass → evidence ([evidence](../../protocol/evidence.md)).
3. Adversarial: risk `low`/`medium` 1, `high`/`critical` 2 bağımsız reviewer;
   max 5 tur ([quality-gates](../../policies/quality-gates.md)).
4. UI'a dokunan fix → UI gate yeniden.
