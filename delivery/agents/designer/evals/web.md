# Designer web — eval set

> En az 10 senaryo. `expert` seviyesi: uç durumu fark eder, gerekçeli öneri
> üretir ve handoff'ta eksik bırakmaz.

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DW-1 | Checkout'ta empty/error state yok | State matrisi + öneri | Yalnız happy path |
| DW-2 | 360px'te yatay scroll | Taşma nedeni + düzeltme | "Mobilde de çalışır" |
| DW-3 | Focus `outline:none` | Görünür focus önerisi | Erişilebilirlik atlaması |
| DW-4 | Kontrast 3.2:1 | AA için renk/token önerisi | "Marka rengi" waive |
| DW-5 | Form hatası ekran okuyucuya gitmiyor | `aria-live`/ilişki önerisi | Sessiz hata |
| DW-6 | LCP görseli 1.8MB | Format/boyut/priority önerisi | Performans yok sayılır |
| DW-7 | Aynı component 3 farklı spacing | Token eşlemesi | Hardcoded değer |
| DW-8 | Handoff'ta copy yok | Copy + durum metinleri | "Developer yazar" |
| DW-9 | Dark mode'da kontrast düşük | Semantic renk önerisi | Ayrı tema yok |
| DW-10 | reduced-motion açıkken animasyon | Alternatif akış | Animasyon zorlanır |
