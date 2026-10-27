# Designer iOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DI-1 | Dynamic Type XXL'de buton taşıyor | Yeniden akış/ölçü önerisi | Sabit yükseklik |
| DI-2 | Sheet yerine full-screen modal | HIG gerekçesi + alternatif | Platform körü |
| DI-3 | Safe area altında CTA | Inset/scroll önerisi | İçerik kesilir |
| DI-4 | VoiceOver sırası ters | Doğru sıra + trait | Yalnız label |
| DI-5 | Dark mode'da hardcoded beyaz | Semantic renk | Kontrast kırılır |
| DI-6 | iPad universal ama layout phone | Size class önerisi | "Aynı görünür" |
| DI-7 | ATT izin metni belirsiz | Amaç + alternatif | Zorlayıcı izin |
| DI-8 | Swipe-back çalışmıyor | Navigation düzeltmesi | Gesture yok sayılır |
| DI-9 | Dokunma hedefi 32pt | 44pt önerisi | Küçük hedef |
| DI-10 | Landscape'te içerik kırpılıyor | Scroll/adaptive öneri | Yalnız portrait |
