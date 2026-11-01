# Tester — Doğrudan dağıtım eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TT-1 | `codesign --verify --deep --strict` uyarı veriyor | İçten dışa imza düzeltmesi | "Yerelde açıldı" |
| TT-2 | `spctl -a -vv` reddediyor | Bilet/staple kontrolü | Görmezden gelme |
| TT-3 | `stapler validate` bilet yok diyor | Notarization yeniden | Sadece submit |
| TT-4 | Temiz makinede ilk açılışta uyarı | Dağıtımı durdur | "Benim makinemde açıldı" |
| TT-5 | Appcast imzasız | İmza ekle | Kanal açık kalır |
| TT-6 | Güncelleme eski veriyi siliyor | Veri koruma testi | Yalnız yeni kurulum |
| TT-7 | Geri dönüş denenmemiş | Önceki sürüme dönüş kanıtı | Plan yok |
| TT-8 | Yalnız DMG test edilmiş, zip edilmemiş | İki paket biçimi | Kör nokta |
| TT-9 | Timestamp yok | `--timestamp` ekle | Sertifika süresi riski |
| TT-10 | Notarization id kaydedilmemiş | Kanıta id yaz | İzlenemez |
