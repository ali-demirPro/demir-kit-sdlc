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
| Onay sorusu yanıtsız | `approval.md` süresi dolunca not yaz, devam |
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
| Gate 3 turda geçmedi | `BUDGET` | böl / ertele / waive sorusu |
| Bağlam sert sınırı | — | oturumu kapat, devir notu yaz |

Aynı soru ikinci kez sorulmaz: cevap issue'da yoksa önce oraya yazılır. İnsan
kapısı "otonomi" gerekçesiyle atlanmaz.

## Delegated kabul sınırı (A1)

Sahip yokken koordinatör şu işleri **vekaleten** kapatabilir:

- `low`/`medium` leaf `leaf-done`, review onayı, closure `pass`, epic PR merge
  ve sürüm bump'ı — hepsi geri alınabilir ve makine kapısıyla kanıtlı.
- Kit-internal / self-improvement lane'de `epic-done`: kabul makine kapısıdır
  (`doctor.sh --strict` + testler + merge edilmiş PR), `I13` kapsamı ürün
  teslimatıdır.

Sınır:

- **Ürün teslimatında `epic-done` kabulü insanda kalır.** Vekâlet leaf, closure
  ve PR'ı bitirir; epic closure `pass` + merge edilmiş PR ile bekler, iş durmaz.
- A0 durumları vekâletle kapatılamaz; geri dönülemez iş bekler.
- Vekâlet iki kez devredilmez: vekil, başka bir vekil atayamaz.
- Sahip döndüğünde vekâleten verilen kararlar tek tek gösterilir; itiraz edilen
  karar geri alınır (revert veya yeni leaf).

İşaret:

```text
delegated: coordinator
reason: sahip yok; low/medium, geri alınabilir
```

Evidence veya closure `notes` alanına bu iki satır yazılır; issue'ya kısa Türkçe
"vekaleten kabul" yorumu düşülür. `human-qa` etiketi sahip karar verene kadar
kalır.

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
- `handoff.py` dönüş özetini ve successor devrini yazar; eşikler
  `context-budget.md` ile aynıdır.
- `approval_sweep.py` süresi dolan onayı kapatır; vekâlet kararı ayrı ve
  işaretli kalır.

## Done when

Yeni bir oturumda eşikler ve durma koşulları tek dosyadan okunur; vekâleten
kapatılan her iş `delegated: coordinator` ile işaretlidir ve geri dönülemez iş
insan kapısında bekler. `doctor.sh --strict` politikayı kayıtlı görür.
