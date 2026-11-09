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
   doğrulamak için açılır (`CONTRACT.md` ve `quality-gates.md` tam okunmaz).
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
- Bütçe ihlali bir kalite bulgusu değil, **duruş** nedenidir: özet yaz, yeni
  oturum aç, işi kaybetme.

## Ölçüm

İki oran tek anlamlıdır; `delivery/scripts/context_metrics.py` bunları üretir.

- `miss_rate = |kaçırılan zorunlu| / (|brief| + |kaçırılan|)`. `brief` yalnız
  kullanılan brief dokümanlarıdır; kullanılmayan brief dokümanı kaçırılan
  değil, fazla okumadır.
- `over_read_rate = (brief dışı token + kullanılmayan brief token) / toplam bağlam token`.
  Payda oturum deltasıdır: önce `.kit/usage-<issue>.json`
  (`input + output + reasoning + cache.read + cache.write`), yoksa
  `usage.py --delta` (`usage.session_delta`); ikisi de yoksa `unknown`.
  Claim anındaki `.orchestration/usage-<issue>.json` toplamdır, delta yerine
  kullanılmaz; yalnız açıkça verilirse `method` alanında `usage-total` olarak
  işaretlenir. Doküman maliyeti `bayt / 4`.
- Oranlar `0..1` aralığındadır. Payda sıfırsa, usage dosyası yoksa veya
  doküman bulunamazsa `unknown` yazılır; sıfır uydurulmaz. `1.0` üstü değer
  `1.0`'a kırpılır ve satır `clamped: true` taşır.

`leaf-done` öncesi `.kit/context-metrics.jsonl` dosyasına tek satır yazılır:

```json
{"brief_docs":[],"clamped":false,"config_digest":"sha256:…","cp":"CP-1","extra_docs":[],"issue":314,"method":"tokens:unknown","miss_rate":"unknown","missed_docs":[],"over_read_rate":"unknown","tokens":"unknown","unused_brief_docs":[]}
```

Satır `issue, cp, brief_docs, unused_brief_docs, extra_docs, missed_docs,
tokens, miss_rate, over_read_rate, clamped, config_digest, method` alanlarını
taşır ve deterministiktir (yol artan sıralı, zaman damgası yok). `config_digest`
`delivery/registry.yaml` sha256'sı ile `delivery/context/index.yaml` sürümüdür.
Dosya `.gitignore` içindedir; depoya girmez. Satır yoksa `transition.py`
`uyari: context-metrics satiri yok` yazar ve geçişi engellemez.

## Done when

Yeni bir leaf'te worker bağlamı 200k token'ı geçmez; her CP `brief.py --cp`
çıktısıyla başlar ve `doctor.sh --strict` politikayı kayıtlı görür.
