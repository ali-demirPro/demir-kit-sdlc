# Süreç rigor etki haritası

Tören ağırlığı tek bir kapıdan seçilir ve altı düğmeye yayılır. Bu sayfa hangi
düğmenin hangi davranışı değiştirdiğini, nerede okunduğunu ve neyi **asla**
değiştirmediğini yazar. Sözleşme: [CONTRACT.md](../CONTRACT.md) I24 · Risk
matrisi: [quality-gates.md](quality-gates.md).

## Tek kapı

- Seçim: `kit.config.yaml` → `process.rigor` = `minimal` | `standard` | `full`.
  Alan yoksa `standard` etkin olur ve kaynak `default` yazılır.
- Yayma: `delivery/rigor.yaml` tek çalışma zamanı kaynağıdır; altı düğme
  oradaki `levels` tablosundan gelir.
- Bir kez seçilir: seviye değişince altı düğme birlikte değişir; düğme düğme
  seviye karıştırılmaz.
- Açık değer ezer: canlı düğmede (`modes.workflow`, `docs.density`,
  `qa.level`, `modes.story_granularity`, `team.size`) `kit.config.yaml` değeri
  yaymayı iki yönde de ezer. Kaynak `kit.config.yaml`, türetilmiş değer
  `rigor:<seviye>` olur.
- Saklanan düğme: `modes.review_mode` yayılır ama kaldıraç değildir.
- Okuyan komut: `doctor --explain rigor` etkin seviyeyi, altı düğmeyi ve her
  birinin kaynağını tek matriste basar.

## Düğme tablosu

`Etki` sütunu tören ağırlığını, `Bugün okuyan` sütunu değeri **bugün** çözen
dosya ya da komutu, `Hedef tüketici` sütunu ise değerin bağlanacağı planlanan
yüzeyi verir. İki sütun ayrıdır: hedef, bugünkü okumanın kanıtı değildir.

| Düğme | minimal | standard | full | Etki | Bugün okuyan | Hedef tüketici |
|-------|---------|----------|------|------|--------------|----------------|
| `modes.workflow` | `minimal` | `standard` | `full` | Zorunlu doküman ve kanıt kümesi; minimal yalnız brief/CP kanıtı, full tam zincir. Kalite kapıları sabit. | yok (yalnız doctor --explain rigor matrisinde görünür) | kalite kapı/kanıt seti |
| `docs.density` | `terse` | `balanced` | `thorough` | Doküman ve yorum derinliği; okuma sınıfları ve "dilim oku" kuralı korunur. | `delivery/scripts/resolver.py` (`effective_docs_density`), `delivery/scripts/brief.py` | bağlı — doküman ve bağlam derinliği |
| `qa.level` | `minimal` | `standard` | `full` | Fazladan test kanıtı ayrıntısı; behavior gate ve test çalıştırma her seviyede zorunlu. | yok (yalnız doctor --explain rigor matrisinde görünür) | `delivery/schemas/leaf.schema.json` (`tests_plan`) |
| `modes.story_granularity` | `coarse` | `balanced` | `fine` | Leaf/CP boyutu; minimal daha büyük CP, full daha küçük CP. | yok (yalnız doctor --explain rigor matrisinde görünür) | `delivery/schemas/leaf.schema.json` (`checkpoints`) |
| `modes.review_mode` | `solo` | `lean` | `full` | Kit'te kaldıraç değil; yalnız CCGS eşlemesi için saklanır. | yok (yalnız doctor --explain rigor matrisinde görünür) | `delivery/rigor.yaml` (`kit_semantics`, saklanır) |
| `team.size` | `individual` | `individual` | `studio` | Aktif agent/varyant kümesi; risk tabanı ve insan kapısı değişmez. | yok (yalnız doctor --explain rigor matrisinde görünür) | `delivery/scripts/capabilities.py`, `delivery/scripts/variants.py` |

Bugün gerçekten bağlı tek düğme `docs.density`'dir: değeri `resolver.py` ve
`brief.py` üzerinden doküman/bağlam derinliğine iner. Diğer beş düğme
`delivery/rigor.yaml` üzerinden yayılır ve `doctor --explain rigor` matrisinde
görünür, ama onları okuyan bir tüketici henüz yok; tablodaki hedefler planlanan
yüzeylerdir. Tüketici bağlantısı ayrı iştir ve bu politika onu bağlanmış gibi
göstermez.

## `modes.review_mode`: saklanır, kaldıraç değil

- Değer (`solo` | `lean` | `full`) yalnız CCGS eşlemesi için saklanır;
  `delivery/rigor.yaml` `kit_semantics` bölümü bunu yazar.
- Gating reviewer sayısını değiştirmez; sayı yalnız riskten gelir.
- `gate_level` CP'ye özel açık seçimdir ve rigor'dan türetilmez; `cp_close`
  varsayılanı `fast` bu politikayla değişmez.
- Etkin matriste `effect: stored` görünür; `doctor --explain rigor` değeri ve
  kaynağını yine satır olarak basar.

## Minimal neyi kısaltır?

`minimal` daha az tören seçer, daha az kapı değil.

### Kısalttığı

- Doküman derinliği: `docs.density: terse`; yorum ve doküman daha kısa yazılır.
- Fazladan kanıt: `qa.level: minimal` yalnız ek test kanıtını kısar;
  `modes.workflow: minimal` yalnız brief/CP kanıtını ister.
- Leaf/CP boyutu: `modes.story_granularity: coarse` daha büyük CP'ye izin
  verir; leaf ve CP sayısı azalabilir.

### Kısaltmadığı

- behavior gate her riskte zorunludur; test önce kırmızı, sonra yeşil yazılır.
- en az 1 reviewer vardır (low/medium); high/critical 2 reviewer alır.
- risk tabanı, `auto_escalate` glob'ları ve insan kapısı aynen geçerlidir
  (CONTRACT I24).
- `tests_plan` case'leri çalışır ve `leaf-done` kanıtsız geçmez.

## Risk tabanı sınırı

Rigor tören ağırlığını değiştirir; risk tabanını düşüremez. Sayı
`delivery/rigor.yaml` `gating` bölümünden ve [quality-gates.md](quality-gates.md)
matrisinden gelir; ikisi aynıdır.

| Risk | Gating reviewer | İnsan kapısı |
|------|-----------------|--------------|
| `low` | 1 | — |
| `medium` | 1 | bütçe aşılırsa |
| `high` | 2 | leaf kapanışı (`reviews.human`) |
| `critical` | 2 | her zaman (`reviews.human` + `human_second`) |

- low/medium 1, high/critical 2 gating reviewer; `full` low/medium'a ikinci
  reviewer eklemez.
- high/critical insan kapısı vardır; `minimal` bunu düşürmez.
- `auto_escalate` glob'ları `delivery/registry.yaml` `risk.auto_escalate`
  altındadır ve rigor'dan bağımsızdır.
- Sözleşme cümlesi aynen: "Rigor seviyesi risk tabanını, `auto_escalate`
  glob'larını veya insan kapısını düşüremez; gating reviewer sayısı yalnız
  riskten gelir (low/medium 1, high/critical 2)." (CONTRACT I24)

## CCGS çelişki tablosu

`delivery/plans/P3.yaml` `risk_conflict` ile aynı beş karar ve aynı verdict:

| CCGS | Kit kararı | Verdict |
|------|------------|---------|
| `modes.review_mode: solo` — hiçbir director/specialist gate açılmaz | low/medium: behavior + 1 adversarial reviewer; high/critical: 2 reviewer + insan | `reject` |
| `qa.level: minimal` — logic/integration hikâyelerinde test istenmez | behavior gate her riskte zorunlu; `tests_plan` case'leri çalışır | `narrow` |
| `modes.workflow: minimal` — minimal rotada `/gate-check` çağrılmaz | behavior + evidence + leaf-done her seviyede zorunlu | `narrow` |
| `modes.rigor` kilitli; `review_mode` ve `team.size` local override | yerel override yalnız doküman/bağlam; evidence, reviewer, risk ve insan kapısı kilitli | `narrow` |
| Varsayılan `modes.rigor: minimal` | varsayılan `process.rigor: standard` (bugünkü davranış) | `diverge` |

## Fallback: sessiz düşüş yok

`doctor --explain rigor` geçersiz `process.rigor` veya çözülemeyen düğmede
`uyarı:` satırı yazar, `standard` seviyesine düşer, nedeni `fallback: standard
(neden)` olarak basar ve **exit 2** döner. Ürün kökünde
(`--product --root <proje>`) örnek:

```text
explain: rigor
uyarı: kit.config.yaml: process.rigor 'extreme' geçersiz — beklenen: minimal, standard, full
fallback: standard (kit.config.yaml: process.rigor 'extreme' geçersiz — beklenen: minimal, standard, full)
level: standard source=fallback
```

- `doctor.sh --strict` geçersiz `delivery/rigor.yaml` veya `process.rigor`
  değerini hata sayar (exit 1).
- `brief.py` ve `resolver.py` aynı düşüşü `warning` ve `fallback` kaynağıyla
  taşır.
- Eksik alan bilinçli varsayılandır ve kaynak `default` yazılır; geçersiz
  yapılandırma ise asla sessizce yutulmaz.
