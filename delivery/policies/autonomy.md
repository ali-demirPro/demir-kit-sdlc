# Otonomi ve delegated kabul

Otonomi **tanımlı** eşiklerde ilerler, tanımlı yerlerde durur. Sahip yokken iş
kilitlenmez: geri alınabilir kararlar vekâleten verilir ve işaretlenir. Geri
dönülemez iş insanda kalır. Bu politika [approval.md](approval.md),
[escalation.md](escalation.md), [context-budget.md](context-budget.md) ve
[quality-gates.md](quality-gates.md) ile birlikte okunur.

## Seviyeler

| Seviye | Ad | Ne zaman | İz |
|--------|----|----------|----|
| A0 | Sor | Aşağıdaki durma koşullarından biri | issue yorumu + `human-qa` |
| A1 | Vekâleten | Sahip yok; iş geri alınabilir | `delegated: coordinator` + kısa Türkçe not |
| A2 | Otonom | Eşikler sağ | `transition` / evidence |

Vekâlet bir seviye atlamaz: A1 kararı da aynı kanıtı ister. A0'a düşen işte
vekâlet istenemez.

## Eşikler (A2 — soru sormadan devam)

| Koşul | Sonraki adım |
|-------|--------------|
| Epic `scope-confirmed`, child listesi net | plan + claim |
| Leaf `agent-approved` + health-check `ready` | `executing` + CP döngüsü |
| CP gate'leri + evidence `pass` | sonraki CP |
| Tüm CP'ler + risk `low`/`medium` + review onayı | `leaf-done` |
| Tüm leaf'ler `leaf-done`/`deferred` | closure (`runbooks/epic-closure.md`) |
| Onay isteği süresi doldu ve cevap yok | `approval_sweep.py` notu; A1 sınırında devam |
| Bağlam eşiği | `context-budget.md`: uyarıda özet, sert sınırda yeni oturum + `handoff.py` |
| Claim lease'i doldu | `escalation.md` `STALE`: `-executing` + not, başka leaf'e geç |

## Durma koşulları (A0 — insan kapısı)

| Durum | Kod | Neden |
|-------|-----|-------|
| Prod deploy, store submit, fiyat, yıkıcı migration, veri silme | — | geri dönülemez; her zaman insan |
| Risk `high`/`critical` leaf kapanışı | — | risk modeli C |
| Güvenlik/auth/veri bulgusu | `SEC` | her zaman insan |
| AC belirsiz/çelişkili veya issue/label eksik | `AC` | tek soru, iki net seçenek |
| Kapsam kayması | `SCOPE` | follow-up issue; sessiz büyütme yok |
| İlgili kapının tur bütçesi doldu | `BUDGET` | böl / ertele / waive sorusu (`quality-gates.md`) |
| Bağlam sert sınırı | — | oturumu kapat, devir notu yaz |

Aynı soru ikinci kez sorulmaz: cevap issue'da yoksa önce oraya yazılır. İnsan
kapısı "otonomi" gerekçesiyle atlanmaz.

## Delegated kabul sınırı (A1)

Sahip yokken koordinatör şu işleri **vekaleten** kapatabilir:

- `low`/`medium` leaf'te review onayı, `leaf-done`, closure `pass`, epic PR
  merge ve sürüm bump'ı — hepsi geri alınabilir ve makine kapısıyla kanıtlı.

Sahip **yok** sayılır: onay isteği `approval_sweep.py` süresini doldurmuş
(`low`/`medium` 60 dk, `high` 240 dk) ve insan cevabı yoksa. `critical` ve geri
dönülemez iş süresizdir; vekâlet istenemez.

Sınır:

- **Ürün teslimatında `epic-done` kabulü insanda kalır (T9).** Kit
  self-improvement lane'de makine kapısı kabul için yeterli değildir; T2 insan
  onayı (`agent-approved`) ve T9 insan kabulü bu lane'de de zorunludur. Vekâlet closure `pass` + merge edilmiş PR'da durur; iş kilitlenmez,
  epic teslime hazır sayılır ve yalnız kabul bekler.
- A0 durumları vekâletle kapatılamaz; geri dönülemez iş bekler.
- Vekâlet iki kez devredilmez: vekil, başka bir vekil atayamaz.
- Sahip döndüğünde vekâleten verilen kararlar tek tek gösterilir; itiraz edilen
  karar geri alınır (revert veya yeni leaf).

İşaret:

```text
delegated: coordinator
reason: sahip yok; low/medium, geri alınabilir
```

Bu iki satır evidence `notes` alanına veya closure raporunun metnine yazılır;
issue'ya kısa Türkçe "vekaleten kabul" yorumu düşülür. Karar issue'da kalır;
`approval_sweep.py` süre dolunca `human-qa` yerine `approval-timeout` yazar.

## Dönüş özeti

İş durduğunda, devredildiğinde veya oturum kapandığında **aynı** özet issue'ya ve
sohbete yazılır; en fazla altı satır:

| Satır | İçerik |
|-------|--------|
| Ne bitti | kapanan leaf'ler + commit/branch |
| Kalan | açık leaf veya issue numaraları |
| Karar | verilen ve vekâleten verilen kararlar |
| Sorun | varsa engel; yoksa "yok" |
| Sıradaki | tek komut veya tek adım |
| Onay | gerekiyorsa iki cümlelik Türkçe soru; yoksa "gerekmiyor" |

Özet teknik kimlik taşımaz (task/dispatch/run); ayrıntı issue'dadır.

## Uygulama

- Politika `delivery/registry.yaml → policies.autonomy` ile kayıtlıdır;
  `CONTRACT.md` Yürütme bölümü bu dosyaya bağlanır.
- `handoff.py` devir notunu (`Leaf`/`Bitti`/`Sıradaki`/`Kararlar`) yazar;
  dönüş özeti aynı bilgiyi altı satırda issue'ya ve sohbete verir. Eşikler
  `context-budget.md` ile aynıdır.
- `approval_sweep.py` süresi dolan onayı kapatır; vekâlet kararı ayrı ve
  işaretli kalır.

## Done when

Yeni bir oturumda eşikler ve durma koşulları tek dosyadan okunur; vekâleten
kapatılan her iş `delegated: coordinator` ile işaretlidir ve geri dönülemez iş
insan kapısında bekler. `doctor.sh --strict` politikayı kayıtlı görür.
