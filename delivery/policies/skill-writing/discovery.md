# Skill discovery

Kardeş politika: `skill-writing.md`. Bu doküman yalnız keşif tarafını anlatır:
agent doğru skill'i çağırsın diye description, isim ve boyut nasıl yazılır.

Kaynak: obra/superpowers v7.0.2 (MIT), `writing-skills/references/discovery.md`.

## 1 — Description ne zaman'ı söyler, ne yapar'ı değil

Description tek soruya cevap verir: "Bu iş için bu skill'i şimdi okumalı mıyım?"
Skill'in akışını özetleyen description bir kısayol yaratır; agent gövdeyi
okumadan özete uyar. Bu yüzden süreç özeti yasak, tetikleyici zorunludur.

```yaml
# Kötü — akışı özetliyor; agent gövdeyi okumadan buna uyar
description: >-
  Use when executing plans - dispatch a subagent per task with review between tasks

# İyi — yalnız tetikleyici
description: >-
  Use when executing implementation plans with independent tasks in the current session
```

Kurallar:

- Üçüncü tekil şahıs yaz; description system prompt'a enjekte edilir.
- Belirtiyi yaz, dile özgü ayrıntıyı yazma: "race condition, timing" iyi;
  "setTimeout kullanıyor" kötü. Skill dile özgüyse bunu tetikleyicide söyle.
- 40–400 karakter; `doctor` bu aralığı ve tetikleyiciyi arar
  (`skill-writing.md` §1).

## 2 — Anahtar kelime kapsamı

Agent aradığı kelimeyi bulabilmeli. Description'a şunları koy:

- Hata mesajları: `ENOTEMPTY`, `Hook timed out`.
- Belirtiler: flaky, hanging, zombie, kirlenme.
- Eş anlamlılar: timeout / hang / freeze; cleanup / teardown / afterEach.
- Gerçek araç ve dosya adları: komut, kütüphane, uzantı.

## 3 — İsim fiil önce

Skill'i yaptığı işle adlandır: `creating-skills`, `condition-based-waiting`,
`root-cause-tracing`. Süreç bildiren `-ing` biçimi iyi çalışır; `skill-creation`
gibi isim tamlaması yerine eylemi yaz.

## 4 — Token bütçesi

Sık yüklenen skill her konuşmaya girer. Hedefler:

| Skill türü | Hedef |
|------------|-------|
| Başlangıç akışı | < 150 kelime |
| Sık yüklenen | < 200 kelime |
| Diğer | < 500 kelime |

Kısaltma yolları: ayrıntıyı kardeş dosyaya taşı, `--help` çıktısını tekrar
etme, başka skill'e atıf yap, aynı desenin ikinci örneğini sil. Ölçüm:
`wc -w skills/<ad>/SKILL.md`.

## 5 — Skill'e atıf açık olsun

Başka skill zorunluysa işaretiyle yaz:

- İyi: `**REQUIRED SUB-SKILL:** Call the <ad> skill.`
- İyi: `**REQUIRED BACKGROUND:** Read <ad> before this step.`
- Kötü: "ilgili skill'e bak" — zorunlu mu, opsiyonel mi belirsiz.
- Kötü: `@skills/<ad>/SKILL.md` — dosyayı hemen yükler, bağlamı yakar.

## Done when

Yeni skill'in description'ı yalnız tetikleyici içeriyor, adı fiil önce, gövdesi
hedef kelime bütçesinde ve zorunlu atıflar açık işaretli.
