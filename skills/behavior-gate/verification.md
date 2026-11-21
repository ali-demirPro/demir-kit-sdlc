# Verification — taze kanıt

`behavior-gate` skill'inin kardeş dokümanı. Kanıt akışı `SKILL.md` ve
`delivery/protocol/evidence.md` içinde; bu doküman "bitti" demeden önce neyin
koşulması gerektiğini yazılı hale getirir.

Kaynak: obra/superpowers v7.0.2 (MIT),
`verification-before-completion/SKILL.md`.

## Demir kural

```
TAZE DOĞRULAMA KANITI OLMADAN TAMAMLANDI İDDİASI YOK
```

Doğrulama komutunu **bu mesajda** koşmadıysan geçtiğini söyleyemezsin. Önceki
koşu, "geçmesi lazım", başka bir ajanın raporu kanıt değildir.

## Kapı işlevi

Her durum iddiasından veya memnuniyet ifadesinden önce:

1. **Belirle:** Bu iddiayı hangi komut kanıtlar?
2. **Koş:** Komutu eksiksiz ve taze koş.
3. **Oku:** Çıktının tamamını ve `exit` kodunu oku; düşüşleri say.
4. **Doğrula:** Çıktı iddiayı destekliyor mu?
   - Hayır → gerçek durumu kanıtıyla söyle.
   - Evet → iddiayı kanıtıyla söyle.
5. **Ancak şimdi:** İddiayı yaz.

Bir adımı atlamak doğrulama değil, yanlış beyandır.

## Yaygın başarısızlıklar

| İddia | Gerekli | Yeterli değil |
|-------|---------|---------------|
| Testler geçti | Test komutu: 0 düşüş | Önceki koşu, "geçmeli" |
| Lint temiz | Lint çıktısı: 0 hata | Kısmi kontrol, tahmin |
| Build başarılı | Build komutu: `exit 0` | Lint geçmesi, log iyi görünmesi |
| Hata düzeldi | Orijinal belirtiyi test et: geçti | Kod değişti, düzeldi varsayımı |
| Regresyon testi çalışıyor | Kırmızı-yeşil döngü görüldü | Test bir kez geçti |
| Agent bitirdi | VCS diff değişikliği gösteriyor | Agent "başarılı" dedi |
| Gereksinimler karşılandı | Satır satır kontrol listesi | Testler geçiyor |

## Kırmızı bayraklar — dur

- "çalışmalı", "muhtemelen", "görünüşe göre" gibi ifadeler.
- Doğrulamadan önce memnuniyet ("Harika!", "Tamam!", "Bitti!").
- Doğrulamadan commit / push / PR.
- Agent başarı raporuna güvenmek.
- Kısmi doğrulamayla yetinmek.
- "Sadece bu sefer".
- Yorgunluk ve işin bitmesini istemek.
- Doğrulama koşmadan başarı ima eden her ifade.

## Desenler

Test:

```
✅ [python3 -m unittest ...] [34/34 geçti] "Testler geçiyor"
❌ "Artık geçmeli" / "Doğru görünüyor"
```

Regresyon testi (kırmızı-yeşil):

```
✅ Yaz → koş (geç) → düzeltmeyi geri al → koş (DÜŞMELİ) → geri yükle → koş (geç)
❌ "Regresyon testi yazdım" (kırmızı görülmeden)
```

Build:

```
✅ [build komutu] [exit 0] "Build geçiyor"
❌ "Lint geçti" (lint derlemeyi kontrol etmez)
```

Devir:

```
✅ Ajan raporu → VCS diff'i kontrol et → değişikliği doğrula → gerçek durumu yaz
❌ Ajan raporuna güven
```

## Nerede uygulanır

Şunlardan önce her zaman: başarı/tamamlık iddiası, memnuniyet ifadesi, commit,
PR, `worker_done`, sonraki göreve geçiş, başka ajana devir.

Kural tam ifadeleri, eş anlamlıları ve başarı ima eden dolaylı cümleleri kapsar.

## Done when

Her tamamlık iddiası bu mesajda koşulmuş bir komutun çıktısına ve `exit` koduna
dayanıyor; kanıt yoksa iddia da yok.
