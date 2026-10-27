# Tester web — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TW-1 | Yalnız Chromium testi | WebKit/Firefox smoke ekler | Tek tarayıcı |
| TW-2 | `waitForTimeout` ile yeşil | Deterministik bekleme | Yarış gizlenir |
| TW-3 | Offline'da beyaz ekran | Hata/retry case'i | Test edilmez |
| TW-4 | Console error var | Fail + trace | Yok sayılır |
| TW-5 | Klavye focus tuzağı | A11y case + fail | Yalnız axe |
| TW-6 | 360px'te taşma | Responsive case | Yalnız desktop |
| TW-7 | LCP budget aşıldı | Ölçüm + blocker | "Yavaş ama olur" |
| TW-8 | Flaky test | Karantina + issue | Silinir |
| TW-9 | Form hatası ekran okuyucuda yok | A11y fail | Görsel kontrol |
| TW-10 | Görsel regresyon screenshot'sız | Baseline + diff | "Geçti" |
