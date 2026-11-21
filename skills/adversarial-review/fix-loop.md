# Fix loop

`adversarial-review` skill'inin kardeş dokümanı. Tur sayısı ve onay biçimi
`SKILL.md` içinde; bu doküman bir turun nasıl koşacağını yazılı hale getirir.

Kaynak: obra/superpowers v7.0.2 (MIT),
`subagent-driven-development/references/fix-loop.md`.

## Giriş

Döngü şu bulgularla başlar: spec ihlali, `blocking` (Critical/Important) bulgu
veya doğrulanmış gerçek boşluk.

İki yol döngüye hiç girmez:

- **Minor / nit:** deftere yazılır (`CP: minor (deferred): <tek satır>`) ve son
  incelemeye devredilir; okunmayan bir toplama sessiz çöpe atmadır. Minor
  döngüye girmez.
- **Planın zorunlu kıldığı bulgu:** kararı controller verir; bulguyu plan
  metniyle tartar, spec bağlayıcıdır, kararı eyleme geçmeden deftere yazar.
  "Plan böyle istiyor" diye bulgu kapatılmaz; planla çelişen düzeltme de
  kararsız gönderilmez.

Geri kalan her şey döngüye girer. Bir tur = bir düzeltme gönderimi + bir
kapsamlı yeniden inceleme. CP başına en fazla **5 tur**.

## Tur 1–3 — aynı implementer'ı sürdür

Bulguları **aynı metinle** gönder. Bağlamı canlıdır: görevi, kodu ve kendi
seçimlerini bilir. Harness canlı ajana mesaj gönderemiyorsa brief yolu, rapor
dosyası yolu ve bulgularla yeni bir implementer başlat; rapor dosyası kalıcı
bellektir.

## Tur 4–5 — taze implementer, daha yetkin model

Brief yolu, rapor dosyası yolu, açık bulgular ve şu çerçeveyle gönder: "Önceki
implementer bu görevi N kez denedi; görev artık sende. Neyin denendiğini rapor
dosyasından oku." Üç sürdürmeden sonra hâlâ açık varsa implementer kendi
sorununu göremiyor demektir; taze göz ve yetkinlik artışı birlikte gelir.

## Her turda

Implementer düzeltir, değişen kodu kapsayan testleri koşar, düzeltme raporunu
aynı rapor dosyasına ekler ve kısa sözleşmeyi döndürür.

Yeniden incelemeden önce rapor dosyasında üç şeyi doğrula:

1. Değişen kodu kapsayan testler.
2. Koşulan komut.
3. Komutun çıktısı.

Üçü de varsa yeniden inceleme gönderilir. Fix mesajında kapsayan test
dosyalarını adıyla söyle; tek satırlık düzeltme tüm suite'i gerektirmez.

## Kapsamlı yeniden inceleme

Yalnız düzeltme diff'ini incele:

```bash
python3 delivery/scripts/review_packet.py --issue <N> --cp CP-1 --commit HEAD --delta <FIX_BASE>
```

`FIX_BASE`, önceki incelemenin gördüğü head'dir. Reviewer her bulgu için
`ADDRESSED` veya `NOT ADDRESSED` yazar ve yalnız düzeltme diff'inde yeni
kırılma arar. Diff'te yeni `blocking` kırılma açık bulgu listesine eklenir;
kapsam dışı gözlemler deftere ertelenmiş minor olarak gider ve döngüyü uzatmaz.

## Koordinatör düzeltmez

Bulgu koordinatör (controller) oturumunda **düzeltilmez**. Koordinatörün bağlamı
koordinasyon için temiz kalır; koordinatör düzeltmesi incelemeden geçmez.
Düzeltme her zaman bir fixer (implementer) görevidir.

## 5. tur sonrası — karar ya da blocked

Beşinci turun yeniden incelemesi hâlâ açık bırakıyorsa gönderim durur
(`SKILL.md`: en fazla 5 tur). Koordinatör açık bulguları iki sınıfa ayırır; plan
ve CP'ler arası bağlam yalnız onda vardır:

- **Koordinatörün karar verebildiği bulgu:** deftere karar yazılır.
  - Reviewer yanlış veya tartışmalı:
    `CP: parked — <bulgu> — Karar: <kod neden duruyor>`. Son inceleme iki tarafı da görür.
  - Gerçek ama bağımlı iş yok: aynı biçimde park et; karar gerçek ve ertelendi der.
  - Gerçek ve taşıyıcı (sonraki iş bunun üstüne kurulur veya plan kusuru ortaya
    çıkar): bağımlı işi açan en küçük değişikliğe karar ver, deftere yaz ve
    sonraki görevin gönderimine taşı. Yapısal kusuru sessizce park etmek, bütün
    bağımlı işleri onun üstüne kurar.
- **Koordinatörün karar veremediği bulgu** (kapsam, sözleşme veya insan kararı
  gerekiyor): leaf `blocked` olur ve issue'ya tek bir insan dili sorusu yazılır.
  Açık bulgular defterde tek satırla listelenir.

Karar yalnız tavanda verilir; döngüyü erken bitirmek için erken karar vermek
ön yargıdır. Her karar bir defter satırıdır; sessiz çöpe atma yasak.

## Aktör adları

Kit sözlüğü: **koordinatör** = controller; **fixer** = implementer. Bu doküman
upstream adları parantez içinde taşır.

## Defter satırı

Her turdan sonra:

```text
CP: fix round <R>/5 (<X> addressed, <Y> open — <bulgu tek satırları>; commit <a7>..<b7>)
```

## Done when

Her zorunlu bulgu `ADDRESSED` veya tavanda defterde karara bağlandı; karar
verilemeyen bulgu kaldıysa leaf `blocked` ve issue'da tek insan sorusu var;
`reviews.adversarial` evidence'a yazıldı.
