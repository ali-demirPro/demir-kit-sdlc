# Skill yazımı

Skill, agent'ın işe başlarken okuduğu ilk yüzeydir. İyi yazılmış bir skill
doğru çağrılır, yanlış yazılmış bir skill ya hiç çağrılmaz ya da yanlış iş
yaptırır. Bu politika `doctor` tarafından denetlenir (`skill writing`).

Kaynak desen: Matt Pocock'un `writing-for-agents` kuralları. Diller: başlıklar
ve YAML anahtarları İngilizce, gövde Türkçe.

## 1 — Description bir context pointer

Description iki parçadan oluşur:

1. **Ne:** tek cümle, skill'in ne yaptığı.
2. **Use when:** her dal için bir tetikleyici.

```yaml
# İyi
description: >-
  Seal a v2 leaf: demir-kit YAML, AC ↔ tests_plan mapping, risk level.
  Use when a leaf needs its seal, when doctor rejects a seal body, or when
  scope must be locked before source work.

# Kötü — tetik yok, agent ne zaman çağıracağını bilemez
description: >-
  Seal a v2 leaf.
```

Tetikleyici ifadeleri: `Use when …`, `Ne zaman …`, `When the …`.

## 2 — Her adım checkable bir koşulla biter

"Kontrol et", "iyi olduğundan emin ol" gibi ifadeler yerine komut, dosya veya
ölçülebilir sonuç yaz: `doctor.sh --strict` sıfır uyarı, `exit 0`, dosya var.

## 3 — Her skill `## Done when` ile biter

Son bölüm, skill'in bittiğini söyleyen tek cümlelik koşuldur. Boş bırakılamaz;
`doctor` bu bölümü arar.

## 4 — Pozitif yaz, yasağı guardrail olarak kullan

Önce hedefi söyle, sonra sert sınırı. "Şunu yapma" tek başına hedef bırakmaz.
Yasak yalnız geri dönüşü olmayan durumlar içindir (kullanıcı verisine yazmak,
onaysız kaynak değişikliği).

## 5 — Gövdeyi böl, ayrıntıyı kardeş dosyaya taşı

Her dalın ihtiyacı olan bilgi gövdede kalır; yalnız bazı dalların ihtiyacı
(`recipes.md`, `existing-app.md`) kardeş dosyaya taşınır ve göreli linkle
bağlanır. Göreli linkler çözülmek zorundadır.

## 6 — Skill çağrısı açık olsun

Bir skill diğerini çağırırken açıkça yazar: "Call the `ui-gate` skill". Örtük
zincir kurmak yerine tek adımda tek skill çağrılır.

## 7 — Boyut

| Satır | Sonuç |
|-------|-------|
| ≤ 200 | normal |
| 201–300 | uyarı |
| > 300 | hata |

Uzun skill bölünür: gövde akışı anlatır, ayrıntı kardeş dosyaya gider.

## Lint

| Kural | Seviye |
|-------|--------|
| frontmatter `description` var | hata |
| description 40–400 karakter | hata |
| description tetikleyici içeriyor | hata |
| `## Done when` var ve boş değil | hata |
| göreli markdown linki çözülüyor | hata |
| gövde ≤ 300 satır | hata (201–300 uyarı) |
| `TODO` / `TBD` yok | uyarı |

Çalıştırma:

```bash
./delivery/scripts/doctor.sh --strict
```

## Done when

Dokuz runtime skill `doctor.sh --strict` altında sıfır uyarı verir ve yeni bir
skill bu tablodaki kuralların tamamından geçer.
