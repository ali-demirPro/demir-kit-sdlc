# Designer macOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DM-1 | Bir komut yalnız toolbar'da, menüde yok | Menüye Command eklenmesi | Klavyeden ulaşılamaz |
| DM-2 | Settings ayrı pencere yerine sheet | Ayrı pencere önerisi | iOS alışkanlığı |
| DM-3 | Sidebar daraltılamıyor | Collapse + durum hatırlama | Sabit genişlik |
| DM-4 | İki farklı yerde aynı komut farklı kısayol | Tek kısayol haritası | Çakışma |
| DM-5 | Dark mode'da sabit beyaz toolbar | Semantic materyal | Kontrast kırılır |
| DM-6 | Content layer'da Liquid Glass | Functional layer'a taşıma | Okunabilirlik düşer |
| DM-7 | Pencere minimum boyutu yok, içerik kırpılıyor | Minimum boyut + scroll | Kırpma |
| DM-8 | Boş ekran "kayıt yok" diyor | İlk eylemi öneren durum | Çıkmaz |
| DM-9 | 44pt dokunma hedefi masaüstüne uygulanmış | macOS ölçüsü | Aşırı seyrek düzen |
| DM-10 | VoiceOver odak sırası menüden başlıyor | İçerik sırası | Anlamsız sıra |
