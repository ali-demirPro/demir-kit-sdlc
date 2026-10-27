# Security — Threat Model

**Capabilities:** `quality.security`, `quality.observability` · **Min level:** expert
**Gate:** `architect` + security review

## Kapsam

Sistematik tehdit modeli, saldırı yüzeyi, tedarik zinciri ve güvenlik
gözlemlenebilirliği.

## Yöntem

1. **Varlıklar:** para, kimlik, veri, itibar; ne korunuyor?
2. **Aktörler:** anonim, kullanıcı, admin, insider, bot.
3. **Trust boundary:** ağ, cihaz, servis, üçüncü parti.
4. **STRIDE:** spoofing, tampering, repudiation, disclosure, DoS, elevation.
5. **Saldırı yüzeyi:** endpoint, upload, webhook, admin, CI.
6. **Tedarik zinciri:** bağımlılık, imza, build izni, SBOM.
7. **Sinyal:** auth fail, anomali, rate limit, alarm.
8. **Bulgular:** `SEC-*` + severity + owner + kapatma kanıtı.

## Kanıt

- Threat model tablosu (varlık/tehdit/kontrol).
- Trust boundary diyagramı.
- Abuse case listesi.
- Supply chain görünürlüğü.
- Açık/kapalı `SEC-*` listesi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Varlık | Kritik varlıklar listeli |
| Boundary | Sınır ve aktör net |
| STRIDE | En az 6 tehdit |
| Abuse | Kötüye kullanım senaryosu |
| Supply | Bağımlılık/imza |
| Sinyal | Anomali alarmı |

## Anti-pattern'ler

- Yalnız OWASP listesi okumak.
- Insider/CI saldırısını atlamak.
- Tehdidi "düşük olasılık" diye kapatmak.
- Supply chain'i görmezden gelmek.
- Bulguyu sahipsiz bırakmak.

## Handoff

Architect'e: boundary/tasarım.
Developer'a: `SEC-*` + fix.
Tester'a: abuse case.
DevOps'a: sinyal/alarm.
