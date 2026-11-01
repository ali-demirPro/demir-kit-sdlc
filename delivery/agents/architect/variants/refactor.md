# Architect — Refactor

**Entry:** `entry.kind: refactor` · **Gate:** `architect`, `behavior`
**Politika:** [refactor-triggers.md](../../../policies/refactor-triggers.md)

## Kapsam

`entry.kind: refactor` ile mühürlenen her leaf. Capability tabanlı bir varyant
değildir; her platformda geçerlidir. Refactor tetiği yoksa leaf açılmaz.

## Girdiler

- Tetik ve ölçümü (hangi eşik, hangi dosya/modül).
- Baseline commit ve mevcut test/snapshot durumu.
- Varsa `ARCHITECTURE.md`, ADR'ler ve modül sınırları.

## Yöntem

1. **Survey (kod değişmez):** hotspot taraması, god model, tek konformerli
   protokol, iki dosyada kopyalanmış tip, `@MainActor`/main thread içinde saf
   mantık. **Deletion test:** modülü silsem karmaşıklık tek yerde mi toplanır
   (tut) yoksa her çağırana mı dağılır (hak ediyor)?
2. **Propose:** kart başına `Strong | Worth exploring | Speculative`; dosyalar,
   sinyal, sorun, öneri, kazanç, aynı davranışın kanıtı, adım planı. Üst öneri
   ve "değerlendirildi, önerilmedi" listesi.
3. **Refactor:** tek adım = tek commit; yeni tip yeni dosyada önce derlenir;
   feature karışmaz; eski yol gerekiyorsa bir milestone flag arkasında kalır.
4. **Record:** `ARCHITECTURE.md` güncel; ADR yalnız geri dönüşü zor, şaşırtıcı
   ve gerçek trade-off varsa.

## Kanıt

- `verification.refactor`: baseline/after, `unchanged: true`, `files_changed`.
- UI'a dokunulduysa eşit snapshot hash'i (`ui_unchanged: true`).
- Değişen modül sınırı için kısa diyagram veya ADR.
- İnceleme kartları issue yorumu olarak (repo'ya dosya eklenmez).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Tetik | Ölçülmüş bir eşik var |
| Kapsam | Tek adım, feature karışmamış |
| Davranış | `unchanged: true`, iki tarafta test pass |
| Boyut | `files_changed` ≤ 10 (11–20 uyarı) |
| Kayıt | `ARCHITECTURE.md` kodla uyumlu |
| Görünüm | UI dokunduysa snapshot hash eşit |

## Anti-pattern'ler

- Tetiksiz "temizlik" leaf'i açmak.
- Refactor içinde davranış düzeltmek (ayrı leaf).
- Dev dosya taşımasını tek commit'te yapmak.
- Kanıtı refactor'dan sonra üretmek (baseline commit'i sonradan seçmek).
- Eski testleri silmeden yenisini üstüne yığmak.

## Handoff

Developer'a: adım planı ve baseline commit. Tester'a: aynı test setinin iki
tarafta koştuğu kanıt. Documenter'a: güncellenen mimari kaydı.
