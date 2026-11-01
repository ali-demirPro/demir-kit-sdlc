# Tester macOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DT-1 | Self-test kullanıcı store'una yazıyor | `/tmp` store + seed | Veri kaybı |
| DT-2 | Snapshot yalnız light modda | light + dark çifti | Eksik kanıt |
| DT-3 | İnaktif pencerenin soluk metni hata sayıldı | Pencereyi key yapıp yeniden çekim | Yanlış bulgu |
| DT-4 | Menü durumu uygulama içinden okunuyor | Dışarıdan erişilebilirlik denetimi | Güvenilmez sonuç |
| DT-5 | Snapshot sayfaları seed'siz, boş | Seed verisi açık | Boş durum kanıtı |
| DT-6 | Self-test exit kodu yok | Exit 0/1 + PASS satırları | Otomasyon kör |
| DT-7 | Açık sheet varken terminate | Önce sheet kapatma | Koşu asılır |
| DT-8 | Crash sonrası saved state silinmiyor | State temizliği | Sonraki koşu takılır |
| DT-9 | Global kısayol testi self-test'te | Debug köprüsü ile | Kapsam dışı kaldı |
| DT-10 | "Elle denedim" ile kapatılan davranış | Adımlı manuel kayıt | Kanıtsız pass |
