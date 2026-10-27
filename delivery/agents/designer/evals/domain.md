# Designer domain — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DD-1 | DE metni butona sığmıyor | Esnek layout | Kırpılma |
| DD-2 | RTL ikon yönü ters | Ayna/ayrı asset | Yanlış yön |
| DD-3 | Çoğul 0/1/2 | Dil kuralı | "1 items" |
| DD-4 | Tarih 03/04/2026 | Locale format | Belirsiz |
| DD-5 | Para birimi karışık | Locale + ISO | Yanlış tutar |
| DD-6 | Pseudo-locale taşması | Test + düzeltme | Sürpriz |
| DD-7 | Metin görselde gömülü | Lokalize katman | Çevrilemez |
| DD-8 | Funnel adımı belirsiz | Event tanımı | Ölçümsüz |
| DD-9 | Event'te email | PII kaldır | Gizlilik |
| DD-10 | Guardrail yok | Metrik ekle | Risk |
