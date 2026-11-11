# Bağlam bütçesi

Token maliyeti, modelin her adımda yeniden okuduğu **bağlam** ile büyür.
Ölçüm (dogfood, 2026-11): tek çalışma 8 epic'i aynı bağlamda yürüttü; bağlam
19k → 823k token'a çıktı, adım başına maliyet 8,5x arttı ve toplam maliyetin
%88'i bağlam 400k'yı geçtikten sonra ödendi. Kural: bağlamı iş sınırında
sıfırla, bir dosyayı bir kez ve yalnız gereken dilimde oku.

## Eşikler

| Ölçü | Uyarı | Sert sınır |
|------|-------|------------|
| Oturum bağlamı | 200k token | 300k token |
| Tek araç çıktısı | 2k token | 8k token |
| Worker başına okunan doküman | 3 dosya | 5 dosya |

Sert sınırda dur: kısa özet yaz (karar + dosya yolları + açık iş), yeni oturum
aç ve özetle devam et. Sessizce devam etmek yasak.

## Üç okuma sınıfı

LSA'nın `sink_size + top_k + window_size` ayrımı bu politikanın okuma
sözleşmesidir. Her dosya tek bir sınıfa girer; sınıfı belirlenemeyen dosya
`unknown` sayılır.

| Sınıf | Ne | Bütçe | Kaynak |
|-------|-----|-------|--------|
| `sink` | Zorunlu çekirdek: seal, AC, testler, gate yolu | CP başına en fazla 4 dosya / 10k token | seal + CP brief |
| `window` | Son CP/leaf'in taze yüzeyi: aktif rol ajan dokümanları | en fazla 3 dosya / 8k token | resolver role docs |
| `retrieved` | Göreve göre seçilen uzun kuyruk | en fazla 5 dosya / 20k token | index/route |
| `unknown` | Sınıfı belirlenemeyen | retrieve edilmez; brief'te görünür | — |

Sınıf bütçeleri mevcut eşikleri değiştirmez: 200k/300k bağlam, 2k/8k araç
çıktısı ve 3/5 doküman sınırları aynen geçerlidir. Bütçeler kodla uygulanır
(`brief.py`): `window` en fazla `WINDOW_LIMIT` (3), route ile seçilen
`retrieved`, her CP için en fazla 5 dosyadır (`READ_BUDGET`); route **6.
dosyayı seçmek isteyince brief durur (`exit ≠ 0`)**, dosyayı sessizce
atarmaz. `sink` zorunlu çekirdektir (`SINK_LIMIT` = 4) ve değişiklik
yüzeyini listeler; `unknown` okunmadığı için toplama girmez. "Worker başına
okunan doküman" eşikleri (3 uyarı / 5 sert) aynen geçerlidir. `READ_BUDGET`
tek kaynaktır: brief'in son talimat satırı ve `.kit/brief-*.json` içindeki
`selected_docs` aynı sabiti ve aynı seçim listesini kullanır; çelişki bir
test ile engellenir.

### CP başına zorunlu sink

Her CP brief'i şu dört sink'i taşır:

1. Seal bloğu (`epic`, `risk`, `surfaces`, `reference.paths`).
2. CP'ye bağlı AC satırları.
3. `tests_plan` içindeki CP test case'leri.
4. `gate.sh --issue N --checkpoint CP-x` gate yolu.

Sink satırları `brief.py --cp` çıktısında `[sink]` etiketiyle görünür. Eksik
sink `unknown` değildir; brief seal düzeltilmeden başlamaz.

### Retrieved seçim kuralı

`retrieved` yalnız route index'ten seçilir: seal `surfaces` ile eşleşen
girdiler weight azalan sırada alınır; eşit weight'te yol artan sıralanır.
Eşleşmeyen veya weight'i eşik altında kalan aday retrieved listesine katılmaz.
Sınıfı belirlenemeyen dosya da `[unknown]` sayılır ve sessizce retrieved'a
düşmez. Seçim `READ_BUDGET` (5) dosyada serttir: route 6. adayı seçmek
isteyince brief `ReadBudgetError` ile durur ve `exit ≠ 0` verir; fazlası
sessizce atılamaz. Büyük dokümanlar **bölüm hedefiyle** yönlendirilir:
index girdisindeki opsiyonel `section` (boş olmayan string) route/brief
çıktısında `path#section` olarak yazılır; worker dosyayı `rg -n` ile yalnız
o başlıkta okur, tamamını açmaz (`CONTRACT.md`, `quality-gates.md`: ağırlık 2
+ bölüm hedefi).

### Etiketler

`brief.py --cp` doküman ve route satırlarını `[sink]`, `[window]`,
`[retrieved]` ve `[unknown]` etiketleriyle yazar. Etiketsiz dosya yoktur;
varsayılan `[unknown]`'dır. "Bir kez oku" ve dilim okuma kuralları aynen
geçerlidir; `unknown` dosya açılmadan önce sınıflandırılır.

## Kurallar

1. **Epic başına yeni bağlam.** Bir epic bitince sonraki epic yeni oturumda
   başlar; `session move` ile bağlam epic'ler arasında taşınmaz. Aynı epic
   içinde CP sınırında özet + yeni oturum serbesttir.
2. **Koordinatör salt-okur.** Orchestrator diff, log veya dosya içeriği okumaz;
   keşfi subagent'a yaptırır ve en fazla 30 satır özet alır. Uygulama işi
   worker'ın oturumunda kalır.
3. **Bir kez oku.** Aynı dosya ikinci kez okunmaz; önceki okumanın özeti
   kullanılır. Tam dosya yerine `rg -n`, `sed -n '40,90p'`, `git diff --stat`.
4. **Çıktıyı sınırla.** Gate/test logu dosyaya yazılır (`> /tmp/gate.log`),
   bağlama yalnız son 40 satır girer. `git diff` tam dökümü yerine dosya başına
   hunk alınır; `gh api` çıktısı `--jq` ile daraltılır.
5. **CP brief ile başla.** Worker, seal'i ve dokümanları kendiliğinden okumaz;
   `brief.py --cp CP-x` çıktısıyla başlar. Doküman yalnız brief'teki satırı
   doğrulamak için açılır; bölüm hedefli satırlar (`path#section`) yalnız o
   başlıkta okunur (`CONTRACT.md` ve `quality-gates.md` tam okunmaz).
6. **Yazma biçimi.** Var olan dosya `edit`/patch ile değişir; tam dosya yazma
   yalnız yeni dosyada kullanılır. Yazılan içerik bağlama ikinci kez girmez.
7. **Kanıt özeti.** Issue'ya ham log değil, komut + exit code + dosya yolu +
   tek satır sonuç yazılır.
8. **Reviewer paketi.** Reviewer tüm repoyu değil, diff + AC + checklist +
   açık bulgular paketini okur. Fix sonrası yalnız delta diff yeniden incelenir.
9. **İstisna.** Güvenlik, ödeme, veri göçü ve geri dönüşü olmayan işlemlerde tam
   dosya okuma serbesttir; gerekçe evidence `notes` alanına yazılır.

## Uygulama

- Politika `delivery/registry.yaml → policies.context_budget` ile kayıtlıdır.
- `brief.py --cp` kompakt CP brief'i üretir; `orca_plan.py` worker spec'ine gömer.
- `usage.py --check --context` claim (`next-leaf.py`) ve CP kapanışında
  (`cp_close.py --apply`) çağrılır; ölçülen değer 300k'yı aşarsa leaf/CP
  kapanmaz, `blocked` etiketi ve gerekçe yorumu yazılır. Ölçüm yoksa kontrol
  atlanır — `unknown` bağlam claim'i/kapanışı engellemez.
- Route `retrieved` seçimi `READ_BUDGET` (5) dosyada serttir; aşım `exit ≠ 0`.
- Büyük dokümanlar için `index.yaml` girdisi `section` ile bölüm hedefi taşır
  ve brief `path#section` yazar; route/brief talimatı tek kaynaktan (`READ_BUDGET`)
  üretilir.
- Bütçe ihlali bir kalite bulgusu değil, **duruş** nedenidir: özet yaz, yeni
  oturum aç, işi kaybetme.

## Ölçüm

İki oran tek anlamlıdır; `delivery/scripts/context_metrics.py` bunları üretir.
`context_metrics.py summary --window 10` son 10 satırdan miss/over-read ortalama +
dağılım, leaf başına `armed`/`fallback_count` üretir; 10'dan az satırda
`ready: false`, ölçülemeyen kalem `ölçülemedi` yazar.

- `miss_rate = |kaçırılan zorunlu| / (|brief| + |kaçırılan|)`. `brief` yalnız
  kullanılan brief dokümanlarıdır; kullanılmayan brief dokümanı kaçırılan
  değil, fazla okumadır.
- `over_read_rate = (brief dışı token + kullanılmayan brief token) / toplam bağlam token`.
  Payda oturum deltasıdır: önce `.kit/usage-<issue>.json`
  (`input + output + reasoning + cache.read + cache.write`), yoksa
  `usage.py --delta` (`usage.session_delta`); ikisi de yoksa `tokens:unknown`.
  Claim anındaki `.orchestration/usage-<issue>.json` toplamdır, delta yerine
  kullanılmaz; yalnız açıkça verilirse `method` alanında `usage-total` olarak
  işaretlenir. Doküman maliyeti `bayt / 4`.
- Oranlar `0..1` aralığındadır. Payda sıfırsa, usage dosyası yoksa veya
  doküman bulunamazsa oran **ölçülemez**: ilgili alan satırda bulunmaz
  (`miss_rate` / `over_read_rate` yazılmaz, `clamped` da yazılamaz) — `unknown`
  yazılmaz, sıfır uydurulmaz. `1.0` üstü değer
  `1.0`'a kırpılır ve satır `clamped: true` taşır.

`leaf-done` öncesi `.kit/context-metrics.jsonl` dosyasına tek satır yazılır:

```json
{"armed":true,"brief_docs":[],"config_digest":"sha256:…","cp":"CP-1","extra_docs":[],"fallback_count":2,"issue":314,"method":"split:unknown;tokens:unknown","missed_docs":[],"selected_docs":["delivery/scripts/brief.py"],"tokens":"unknown","unused_brief_docs":[]}
```

Satır `issue, cp, selected_docs, brief_docs, unused_brief_docs, extra_docs,
missed_docs, tokens, armed, fallback_count, config_digest, method` alanlarını
taşır ve ölçülebilen `miss_rate`, `over_read_rate` ve `clamped` alanları
onların yanında yer alır; deterministiktir (yol artan sıralı,
zaman damgası yok). `selected_docs` brief'in seçtiği dokümanlardır; `brief_docs`
yalnız kullanıldığı kanıtlananlar, `unused_brief_docs` seçilip kullanılmayanlar,
`extra_docs` brief dışından okunanlardır (`brief_docs` boş olabilir). `armed`
brief'in etkin seçim yapıp yapmadığıdır (bool ya da `unknown`), `fallback_count`
üretilen fallback uyarısı sayısıdır (int ya da `unknown`); metadata yoksa veya
değer liste değilse `unknown` yazılır, `false`/`0` uydurulmaz. `config_digest`
`delivery/registry.yaml` sha256'sı ile `delivery/context/index.yaml` sürümüdür.

CP brief seçimini `.kit/brief-<issue>-<cp>.json` dosyasına da yazar; anahtarlar
`issue`, `cp`, `armed`, `unarmed`, `fallbacks`, `selected_docs` ve değerler
deterministiktir. Bu dosya yalnız seçimi bilir; kullanım kanıtı üretmez.
`.kit/brief-*.json` ve `.kit/context-metrics.jsonl` ana checkout `.kit` altında
yaşar (cycle.jsonl gibi); epic worktree kaldırılınca kaybolmaz.

`usage_known` / `split:unknown` kuralı: brief metadata'sı yalnız seçimi bilir.
Kullanım kanıtı yoksa `brief_docs` ve `unused_brief_docs` boş olur, `miss_rate` ve
`over_read_rate` alanları satırda bulunmaz ve `method` `split:unknown` taşır; `0.0`
uydurulmaz. `tokens` yine usage deltasından gelebilir, çünkü bilinmeyen yalnız
used/unused ayrımıdır.

Yazma `.kit/context-metrics.lock` üzerinde `fcntl.flock` ile serileşir; okuma
hatasında dosya değiştirilmez ve hata bildirilir (`ContextMetricsError`).
`.kit/context-metrics.jsonl.tmp` ve `.kit/brief-*.json` `.gitignore`
kapsamındadır; depoya girmez. `transition.py` leaf-done öncesi önce
`.kit/brief-<issue>-<cp>.json` metadata'sından satır üretmeyi dener; satır zaten
varsa dokunmaz (usage kanıtıyla yazılmış satır ezilmez). Satır yine yoksa
`uyari: context-metrics satiri yok` yazar ve geçişi engellemez — varsayılan
leaf-done davranışı budur. `transition.sh --require-metrics` seçildiğinde satır
yoksa geçiş durur; bu bayrak leaf sahibinin açık tercihidir, varsayılan değildir.

## Done when

Yeni bir leaf'te worker bağlamı 200k token'ı geçmez; her CP `brief.py --cp`
çıktısıyla başlar ve `doctor.sh --strict` politikayı kayıtlı görür.
