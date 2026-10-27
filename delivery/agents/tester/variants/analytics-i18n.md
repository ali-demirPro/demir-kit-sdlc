# Tester — Analytics / i18n

**Capabilities:** `domain.analytics`, `domain.i18n` · **Min level:** practitioner
**Gate:** `behavior`

## Kapsam

Event/funnel doğruluğu ve çok dilli arayüzün davranışı.

## Yöntem

1. Event adı/şeması; duplicate/eksik event.
2. Funnel adımları; drop-off.
3. PII ve consent: red edilince ölçüm davranışı.
4. Locale biçimleri: tarih/para/sayı.
5. RTL yön/ikon/hizalama.
6. Metin genişlemesi +%40.
7. Çoğul/cinsiyet.
8. Pseudo-locale smoke.

## Kanıt

- Event/funnel testi.
- PII/consent kontrolü.
- Locale/RTL screenshot'ı.
- Uzun metin testi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Event | Şema/tekrar |
| Funnel | Adımlar |
| PII | Yok |
| Consent | Uyumlu |
| RTL | Doğru |
| Uzun metin | Taşma yok |

## Anti-pattern'ler

- Event'i yalnız geliştirici ortamında test etmek.
- PII'yi property'de bırakmak.
- RTL'i yalnız ayna ile çözmek.
- Sabit genişlik.
- Çeviriyi test etmemek.

## Handoff

Growth/run'a: funnel.
Developer'a: locale/RTL.
Privacy'ye: consent.
