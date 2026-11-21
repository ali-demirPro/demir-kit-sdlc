# TDD disiplini

`behavior-gate` skill'inin kardeş dokümanı. Kapı komutu ve kanıt akışı
`SKILL.md` içinde; bu doküman kırmızı-önce kuralını yazılı hale getirir.

Kaynak: obra/superpowers v7.0.2 (MIT), `test-driven-development/SKILL.md` ve
`test-driven-development/writing-good-tests.md`.

## Demir kural

```
ÖNCE KIRMIZI TEST, SONRA ÜRETİM KODU
```

Testten önce kod yazdıysan sil ve baştan başla.

**İstisna yok:**

- "Referans" olarak tutma.
- Test yazarken "uyarla".
- Ona bakma.
- Sil, silmek silmektir.

Kuralın harfini çiğnemek ruhunu çiğnemektir. "Sadece bu sefer" bir gerekçe
değil, ihlalin adıdır.

## RED — testi yaz ve düş

Bir davranış, açık isim, gerçek kod (zorunlu değilse mock yok).

Testi koş ve **düşüşü gör**. Onayla:

- Test hata veriyor, çöküyor değil.
- Hata mesajı beklediğin mesaj.
- Düşüş nedeni eksik özellik, yazım hatası değil.

Test hemen geçtiyse mevcut davranışı test ediyorsun; testi düzelt. Test hata
veriyorsa hatayı düzelt ve doğru düşene kadar koş.

## GREEN — minimal kod

Testi geçecek en küçük kodu yaz. Özellik ekleme, başka kodu refactor etme,
"iyileştirme" yapma. Test düşerse kodu düzelt, testi değil.

## Verify GREEN — tüm suite

Yalnız kendi testin değil, projenin test komutu yeşil olmalı:

```bash
python3 -m unittest discover -s delivery/tests
```

Görevin kapsamı teslim edilebilir işi sınırlar, doğrulamayı sınırlamaz. Bu koşuda
gördüğün her kırmızı — senin sebep olmadığın dahil — raporda adıyla yazar.
Görüp susmak raporu eksik yazar.

## REFACTOR

Yeşilden sonra: tekrarı kaldır, isimleri düzelt, yardımcı çıkar. Davranış
ekleme. Testler yeşil kalır.

## İyi test

| Nitelik | İyi | Kötü |
|---------|-----|------|
| Minimal | Tek şey; isimde "ve" varsa böl | `test('email ve domain ve boşluk doğrular')` |
| Açık | Davranışı adlandırır | `test('test1')` |
| Niyet | İstenen API'yi gösterir | Kodu belirsizleştirir |

Testi yazmadan önce şunu söyle: "Hangi üretim değişikliği bu testi düşürür?"
Cevap yoksa test bir şey kanıtlamıyor.

## Gerekçe tablosu

| Mazeret | Gerçek |
|---------|--------|
| "Test etmek için çok basit" | Basit kod bozulur; test 30 saniye. |
| "Sonra test ederim" | Sonradan yazılan test hemen geçer; hiçbir şey kanıtlamaz. |
| "Sonradan test aynı amaca hizmet eder" | Sonradan test "bu ne yapıyor", önce test "ne yapmalı"yı ölçer. |
| "Elle zaten denedim" | Elle test kayıtsız, tekrarlanamaz, baskı altında eksik kalır. |
| "X saati silmek israf" | Batık maliyet; güvenilir kod için TDD ile yeniden yaz. |
| "Referans olarak tutayım" | Uyarlarsın; o sonradan testtir. Sil. |
| "TDD beni yavaşlatır" | Kısa yol üretimde hata ayıklamaktır; daha yavaş. |
| "Mevcut kodda test yok" | İyileştiriyorsun; mevcut davranışa test ekle. |

## Kırmızı bayraklar — dur ve baştan başla

- Testten önce kod.
- Uygulamadan sonra test.
- Test hemen geçti.
- Neden düştüğünü açıklayamıyorum.
- "Sonra eklerim".
- "Sadece bu sefer".
- "Elle zaten denedim".
- "Önemli olan ruh, ritüel değil".
- "Bu farklı çünkü…".

Hepsi aynı anlama gelir: kodu sil, TDD ile baştan başla.

## Hata düzeltme

Önce hatayı tekrar üreten kırmızı testi yaz, düşüşü gör, sonra düzelt. Test
düzeltmeyi kanıtlar ve regresyonu engeller. Testsiz hata düzeltmesi yok.

## Kontrol listesi

- [ ] Her yeni fonksiyonun testi var.
- [ ] Her test uygulamadan önce düştü.
- [ ] Düşüş nedeni beklenen nedendi.
- [ ] Testi geçecek minimal kod yazıldı.
- [ ] Tüm suite yeşil, çıktı temiz.
- [ ] Kenar ve hata durumları kapsandı.

Kutuların hepsi işaretlenmiyorsa TDD atlandı; baştan başla.

## Done when

Kapı komutu `exit 0` verdi, test önce kırmızıydı, düşüş nedeni beklenen nedendi
ve tüm suite yeşil.
