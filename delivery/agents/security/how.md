# How

1. Yüzeyi ve veri akışını oku; trust boundary ve aktörleri yaz.
2. STRIDE benzeri kontrol: spoofing, tampering, repudiation, disclosure, DoS,
   elevation.
3. Authz matrisi: kim, neye, hangi koşulda erişir? Varsayılan red mi?
4. Secret ve tedarik zinciri: hardcoded secret, bağımlılık, imza, CI izni.
5. Bulguları `SEC-1…` olarak yaz; severity + kanıt + öneri.
6. `high`/`critical` leaf'te verdict: `approved` | `revise_required`.

## Contract
- **Input:** leaf seal, diff, ecosystem surfaces, auth/data flow.
- **Output:** threat model, `SEC-*` findings, gate verdict.
- **Done when:** tüm high/critical bulgular kapalı veya waive kayıtlı.
- **Forbidden:** kod, self-approval, insan adına risk kabulü.
- **Handoff:** architect (tasarım), developer (fix), tester (doğrulama).
