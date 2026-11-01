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

Tetikleyici ifadeleri (doctor bunları arar):

| İfade | Örnek |
|-------|-------|
| `Use when …` | `Use when a leaf needs its seal.` |
| `Use this skill when …` | `Use this skill when the gate fails.` |
| `Use the skill when …` | `Use the skill when a review is open.` |
| `Use whenever …` | `Use whenever a seal is rejected.` |
| `Ne zaman …` | `Ne zaman mühür gerekliyse.` |
| `Şu durumda kullan …` | `Şu durumda kullan: gate kırmızı.` |

Olumsuz ifade tetikleyici sayılmaz: `Do not use when …`, `Never use when …`,
`Don't use when …`, `asla`, `değil`.

## 2 — Her adım checkable bir koşulla biter

"Kontrol et", "iyi olduğundan emin ol" gibi ifadeler yerine komut, dosya veya
ölçülebilir sonuç yaz: `doctor.sh --strict` sıfır uyarı, `exit 0`, dosya var.

## 3 — Her skill `## Done when` ile biter

Skill'in son bölümü, bittiğini söyleyen kısa bir koşuldur. Tek paragraftır: alt
başlık içermez ve arkasından hiçbir başlık (herhangi bir seviye) gelmez. Boş
bırakılamaz; `doctor` bu bölümü arar.

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

| Gövde satırı | Sonuç |
|--------------|-------|
| ≤ 200 | normal |
| 201–300 | uyarı |
| > 300 | hata |

Uzun skill bölünür: gövde akışı anlatır, ayrıntı kardeş dosyaya gider. Sayım
frontmatter sonrası gövde üzerinden yapılır.

## 8 — Kapsam

Lint her `skills/<name>/SKILL.md` dizinini denetler: `skills.runtime` ve
`skills.scoped` (capability'ye bağlı skill'ler) aynı sözleşmeye tabidir. Kapsam dışı kalan dosyalar bilinçlidir:

- `delivery/agents/<rol>/SKILL.md` rol işaretçisi dokümanlardır; sözleşme
  metinleri `how.md` içindedir ve `doctor` `role contracts` kontrolüyle
  (`registry.role_order_default` rolleri) denetlenir.
- `delivery/orchestrator/how.md` bu denetimin **dışındadır**; orchestrator
  `role_order_default` içinde değildir.
- `delivery/packs/*/checklist.md` ve `delivery/protocol/*.md` skill değildir;
  kendi gate ve protokol kurallarıyla denetlenir.

İki set karıştırılmaz: `## Done when` runtime skill sözleşmesidir, rol
dokümanları `## Contract` kullanır.

## Lint

| Kural | Seviye |
|-------|--------|
| frontmatter `description` var | hata |
| description 40–400 karakter | hata |
| description tetikleyici içeriyor | hata |
| `## Done when` var, boş değil ve son bölüm | hata |
| göreli markdown linki çözülüyor | hata |
| referans kullanımının tanımı var | hata |
| gövde ≤ 300 satır | hata (201–300 uyarı) |
| `TODO` / `TBD` yok | uyarı |

Kod blokları (üç ve daha fazla backtick/tilde, iç içe dahil) ve HTML yorumları
taranmaz: örnek olarak yazılmış bir `## Done when` bölüm sayılmaz, örnekteki
kırık link hata vermez. Link biçimleri: satır içi, başlıklı (parantezli başlık
dahil), açılı parantezli ve referans tanımlı. Sorgu ve çapa kısmı (`?plain=1`,
`#risk`) yok sayılır; dış `http(s)` linkleri denetlenmez.

Çalıştırma:

```bash
./delivery/scripts/doctor.sh --strict
```

## Done when

Dokuz runtime skill `doctor.sh --strict` altında sıfır uyarı verir ve yeni bir
skill bu tablodaki kuralların tamamından geçer.
