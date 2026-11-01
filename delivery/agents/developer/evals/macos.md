# Developer macOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DV-1 | `Task.detached` içinden UI güncellemesi | MainActor'a taşıma | Data race |
| DV-2 | SwiftData alanına varsayılansız ekleme | Varsayılan değer + migration | Açılış çöker |
| DV-3 | Sandbox kapalı, dosya yolu doğrudan | Bookmark + entitlement | Dağıtımda kırılır |
| DV-4 | Uzun iş main thread'de | Actor/arka plan | UI donar |
| DV-5 | Test kullanıcı veritabanına yazıyor | `/tmp` store | Veri kaybı |
| DV-6 | Build yalnız Xcode GUI'sinden | CLI build betiği | Tekrarlanamaz |
| DV-7 | Debug çıktısı stdout'ta, bayraksız | stderr + ortam bayrağı | Gürültü |
| DV-8 | `NSViewRepresentable` tüm ekranı sarıyor | Dar köprü sınırı | Test edilemez |
| DV-9 | Force unwrap ile API yanıtı | Doğrulama + hata yolu | Çökme |
| DV-10 | İmza adımı betikte yok | codesign + notarize adımı | Dağıtımda ret |
