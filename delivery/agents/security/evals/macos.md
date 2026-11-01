# Security macOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| SM-1 | Sandbox kapalı | Açmayı zorunlu kıl | "Gerekmiyor" |
| SM-2 | Keyfi yol erişimi | Bookmark önerisi | Geniş izin |
| SM-3 | Hardened runtime yok | Açma adımı | Notarize hatası |
| SM-4 | İmza anahtarı repoda | Kısa ömürlü kimlik | Sızıntı |
| SM-5 | Appcast imzasız | İmza ekle | Araya girme |
| SM-6 | Geniş entitlement | Minimuma indir | Gerekçesiz |
| SM-7 | İçten dışa imza yok | Sıra düzeltmesi | Doğrulama hatası |
| SM-8 | Bilet staple'sız | Staple adımı | `spctl` ret |
| SM-9 | Log'da kullanıcı verisi | Temizle | Gizlilik ihlali |
| SM-10 | Güncelleme bütünlüğü yok | Hash/imza | Sessiz bozulma |
