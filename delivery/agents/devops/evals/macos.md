# DevOps macOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| VM-1 | Build yalnız Xcode GUI'den | CLI betiği | Tekrarlanamaz |
| VM-2 | `.app` paketlenmiyor | Paketleme adımı | Çalıştırılamaz |
| VM-3 | İmza sırası yanlış | İçten dışa | Reddedilir |
| VM-4 | Timestamp yok | Ekle | Sertifika riski |
| VM-5 | Zip staple deneniyor | `.app`'i önce staple et | Hata |
| VM-6 | DMG staple'sız | Staple adımı | `spctl` ret |
| VM-7 | Temiz makine testi yok | `spctl` doğrulaması | Kör nokta |
| VM-8 | Appcast imzasız | İmzala | Araya girme |
| VM-9 | Geri dönüş planı yok | Önceki sürüm | Kilitlenme |
| VM-10 | Notarization id kaydedilmiyor | Kanıta yaz | İzlenemez |
