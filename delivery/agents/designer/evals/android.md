# Designer Android — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DA-1 | Edge-to-edge'de CTA system bar altında | Inset/padding önerisi | İçerik kesilir |
| DA-2 | Predictive back desteği yok | Back modeli önerisi | Eski davranış |
| DA-3 | Font scale 2.0'da taşma | Yeniden akış | Sabit dp |
| DA-4 | TalkBack sırası anlamsız | Semantics önerisi | Yalnız contentDescription |
| DA-5 | Tablet/foldable phone layout | Window size class önerisi | Tek layout |
| DA-6 | Material 3 yerine iOS deseni | M3 eşlemesi | Platform körü |
| DA-7 | İzin reddi akışı yok | Alternatif akış | Çıkmaz |
| DA-8 | Play data safety ile izin çelişiyor | Tutarlı veri akışı | Çelişki |
| DA-9 | Dynamic color marka rengini bozuyor | Tonal/fallback önerisi | Okunmaz |
| DA-10 | Landscape'te navigation drawer kilitli | Adaptive öneri | Yalnız portrait |
