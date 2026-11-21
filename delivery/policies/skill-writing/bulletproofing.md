# Bulletproofing

Kardeş politika: `skill-writing.md`. Bu doküman disiplin kuran skill'lerin
baskı altında delinmesini engeller.

Kaynak: obra/superpowers v7.0.2 (MIT), `writing-skills/references/bulletproofing.md`.

## Kapsam

Bu araç seti yalnız **disiplin başarısızlığı** içindir: agent kuralı bilir,
baskı altında atlar. Eksik öğe veya yanlış biçimli çıktı sorununda yasak
listesi ters teper; o durumda beklenecek biçimi örnekle göster.

## 1 — Boşluğu açıkça kapat

Kuralı söylemek yetmez; bilinen kaçış yolunu tek tek yasakla:

```markdown
Testten önce kod mu yazdın? Sil. Baştan başla.

**İstisna yok:**
- "Referans" olarak tutma
- Test yazarken "uyarlama"
- Ona bakma
- Sil, silmek silmektir
```

## 2 — "Ruh / harf" tartışmasını erken kes

Skill'in başına temel ilkeyi koy:

> Kuralın harfini çiğnemek, ruhunu çiğnemektir.

Bu cümle, "ruhu yerine getiriyorum" gerekçelerinin bütün sınıfını kapatır.

## 3 — Gerekçe tablosu kur

Baseline testinde agent'ın söylediği her mazeret tabloya girer:

| Mazeret | Gerçek |
|---------|--------|
| "Test etmek için çok basit" | Basit kod da bozulur; test 30 saniye sürer. |
| "Sonra test ederim" | Hemen geçen test hiçbir şey kanıtlamaz. |
| "Sonradan test aynı amaca hizmet eder" | Sonradan test "bu ne yapıyor"u, önce test "ne yapmalı"yı ölçer. |

Kaynak: kendi baseline testin; başka projeden tablo kopyalama.

## 4 — Kırmızı bayrak listesi

Agent kendini kontrol edebilsin diye kısa liste yaz:

```markdown
## Red flags — dur ve baştan başla

- Testten önce kod
- "Elle zaten denedim"
- "Sonradan test aynı işi görür"
- "Önemli olan ruh, ritüel değil"
- "Bu farklı çünkü…"

Hepsi aynı anlama gelir: kodu sil, TDD ile baştan başla.
```

## 5 — Description'a ihlal belirtisi ekle

Kuralı çiğnemek üzere olma belirtisini tetikleyiciye yaz:

```yaml
description: >-
  Use when you wrote code before tests, when tempted to test after, or when
  manual testing feels faster.
```

## 6 — Formu başarısızlığa eşle

| Başarısızlık | Doğru araç |
|--------------|------------|
| Kural biliniyor, atlanıyor | Açık yasak + kırmızı bayrak + gerekçe tablosu |
| Öğe eksik / biçim yanlış | Beklenen biçimin örneği, kontrol listesi |
| Yanlış skill çağrılıyor | Description ve isim düzeltmesi (`discovery.md`) |

Yanlış araca yasak eklemek skill'i uzatır, sorunu çözmez.

## Done when

Skill'de bilinen her kaçış yolu açık bir yasakla kapatıldı, gerekçe tablosu ve
kırmızı bayrak listesi baseline testinden geldi, description ihlal belirtisini
taşıyor.
