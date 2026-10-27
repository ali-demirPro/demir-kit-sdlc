# Security risk — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| SR-1 | Oturum süresi sonsuz | Ömür/iptal/refresh | "Token var" |
| SR-2 | MFA yalnız login | Kritik işlem MFA | Bypass |
| SR-3 | Ödeme retry duplicate | Idempotency key | Çift çekim |
| SR-4 | Refund herkese açık | Yetki + audit | Suistimal |
| SR-5 | Data map yok | Sınıflandırma/retention | "Sonra" |
| SR-6 | PII analytics'te | Minimize/ayrıştır | Gizlilik ihlali |
| SR-7 | Consent geri çekilemiyor | Akış + kayıt | Karanlık desen |
| SR-8 | Privacy label çelişkisi | Tutarlı veri akışı | Store reddi |
| SR-9 | Supply chain imzasız | SBOM/imza | Risk |
| SR-10 | Tehdit sahipsiz | Owner + kapatma | Açık kalır |
