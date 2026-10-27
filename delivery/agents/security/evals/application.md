# Security application — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| SA-1 | IDOR: başka tenant kaydı | Authz testi + fix | UI kontrolü |
| SA-2 | Admin endpoint yalnız login | Rol/izin kontrolü | Auth açığı |
| SA-3 | `innerHTML` kullanıcı verisi | Encoding/CSP | XSS |
| SA-4 | URL fetch kullanıcıdan | SSRF allowlist | Açık fetch |
| SA-5 | Secret repo'da | Rotasyon + temizlik | Kabul |
| SA-6 | Kritik CVE | Upgrade/waive gerekçesi | Yok sayılır |
| SA-7 | Login rate limit yok | Limit + lockout | Brute force |
| SA-8 | CORS `*` + credentials | Origin allowlist | Açık |
| SA-9 | Upload tipi kontrolsüz | Tip/boyut/AV | Açık |
| SA-10 | Mobil token UserDefaults | Keychain | Düz metin |
| SA-11 | Privacy manifest boş | Data map/manifest | Eksik |
| SA-12 | Webhook imzasız | İmza/replay | Sahte ödeme |
