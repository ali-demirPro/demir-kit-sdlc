# Tester — macOS

**Capability:** `platform.macos` · **Min level:** expert
**Gate:** `behavior`, `ui` (varsa), platform

## Kapsam

Masaüstü uygulamasında davranış kanıtı: birim test, self-test, snapshot ve
gerektiğinde debug köprüsü. Simülatör yoktur; gerçek pencere ve gerçek store
vardır.

## Girdiler

- Leaf seal, `tests_plan` case'leri ve `ui_scope`.
- Uygulamanın çalıştırma biçimi (bundle yolu, ortam bayrakları).
- Test store yolu (`/tmp`), seed verisi, snapshot klasörü.

## Yöntem

1. **Birim test:** saf mantık, sabit saat ve sabit store yolu ile.
2. **Self-test:** `--selftest` bayrağı; PASS/FAIL satırları ve exit 0/1.
   Kullanıcı verisine asla dokunmaz.
3. **Snapshot:** light ve dark, sayfa başına PNG; seed verisi açık.
   İnaktif pencere review sayılmaz.
4. **Menü denetimi:** her komutun başlığı ve kısayolu; menü durumu içeriden
   değil, dışarıdan erişilebilirlik ile doğrulanır.
5. **Debug köprüsü:** self-test'in ulaşamadığı global kısayol, panel, izin ve
   zamanlama için; durumu dosyaya yazar.
6. **Asılı kalan koşular:** saved state silinir, çıktı satır tamponlu, açık
   sheet kapatılmadan uygulama sonlandırılmaz.

## Kanıt

- Self-test çıktısı (satır satır) ve exit kodu.
- Snapshot yolları + layout dosyaları; light/dark çifti.
- Menü matrisi: komut, başlık, kısayol, durum.
- Hangi kontrolün manuel yapıldığı ve kimin yaptığı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Birim | Mantık testleri yeşil, saat/store sabit |
| Self-test | Exit 0, her adım PASS |
| Snapshot | Her dokunulan sayfa light+dark |
| Menü | Başlık ve kısayol eşleşiyor |
| İzolasyon | Test store `/tmp`, kullanıcı verisi korunmuş |
| Tekrar | Aynı komut iki kez yeşil (dalgalanma yok) |

## Anti-pattern'ler

- Ekran görüntüsünü tam ekran alıp başka pencereleri kanıta sokmak.
- Kullanıcının gerçek veritabanına karşı test koşmak.
- İnaktif pencerenin soluk metnini "hata" saymak.
- Menü durumunu SwiftUI içinden okumaya çalışmak.
- Self-test'i olmayan davranışı "elle denedim" ile kapatmak.

## Handoff

Developer'a: kırılan adım ve komut.
Release'e: dağıtım öncesi son self-test + snapshot seti.
