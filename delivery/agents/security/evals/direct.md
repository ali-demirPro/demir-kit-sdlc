# Security — Doğrudan dağıtım eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| SD-1 | Hardened runtime kapalı | Açmayı zorunlu kıl | "Notarize olmuyor" |
| SD-2 | Geniş entitlement listesi | Minimum yetkiye indir | Gerekçesiz |
| SD-3 | Temporary exception ile notarize | İstisnayı kaldır | Kalıcı çözüm yok |
| SD-4 | İmza anahtarı repoda | Kısa ömürlü CI kimliği | Sır sızıntısı |
| SD-5 | Appcast imzasız | İmzalı appcast | Araya girme riski |
| SD-6 | İndirme bütünlüğü doğrulanmıyor | Hash/imza kontrolü | Sessiz bozulma |
| SD-7 | İç içe framework dıştan içe imzalanmış | İçten dışa | Doğrulama hatası |
| SD-8 | Log'da kullanıcı verisi | Log temizliği | Gizlilik ihlali |
| SD-9 | Kanal ele geçirilirse plan yok | Geri alma + duyuru planı | Belirsiz |
| SD-10 | Sandbox kapalı | Gerekçe veya açma | Sınırsız erişim |
