# Architect macOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DA-1 | Saf mantık App hedefinde, test edilemiyor | Kit hedefi önerisi | UI'sız test yok |
| DA-2 | İki süreç aynı store'a yazıyor | Tek yazıcı + köprü | Bozulma riski |
| DA-3 | Migration planı yok | Şema geçiş planı | Veri kaybı |
| DA-4 | Güncelleme kanalı belirsiz | Tek kanal + gerekçe | Dağıtım kaosu |
| DA-5 | Sandbox entitlement listesi şişkin | Minimum yetki | Saldırı yüzeyi |
| DA-6 | Store yolu üç dosyada tanımlı | Tek kaynak | Tutarsızlık |
| DA-7 | Arka plan işi App Nap'i yok sayıyor | NSBackgroundActivityScheduler | İş kesilir |
| DA-8 | Açılış süresi hedefi yazılmamış | Ölçülebilir NFR | Doğrulanamaz |
| DA-9 | ADR olmadan geri dönüşü zor karar | ADR kaydı | Kayıp gerekçe |
| DA-10 | `ARCHITECTURE.md` kodla uyuşmuyor | Güncel kayıt | Yanlış harita |
