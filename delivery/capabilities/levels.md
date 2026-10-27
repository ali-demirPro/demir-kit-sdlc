# Capability levels

Bu dosya **seviye doktrini**dir: bir rolün bir yetenekte hangi derinlikte
çalıştığını, neyi kanıtladığını ve hangi kapıyı açabildiğini tanımlar.
Seviye bir kıdem etiketi değil, **kanıtlanmış davranış**tır.

## Seviyeler

| Seviye | Anlam | Yapabilir | Yapamaz | Tipik kanıt |
|--------|-------|-----------|---------|-------------|
| `aware` (L1) | Farkında | Terimleri, riskleri ve checklist'i bilir; gözetim altında uygular | Tek başına gate açamaz | Checklist, referans notu, review |
| `practitioner` (L2) | Uygulayıcı | Standart durumda bağımsız uygular; test/kanıt yazar | Sıra dışı tradeoff'u tek başına kararlaştıramaz | Behavior testi, evidence, 1 reviewer |
| `expert` (L3) | Uzman | Uç durumları, tradeoff'ları ve hata modlarını yönetir; başkasını review eder | İnsan adına risk kabul edemez | 2 reviewer / architect onayı, ADR, edge-case testi |
| `authority` (L4) | Otorite | Standardı belirler, çakışan kararları çözer, kurumsal riski sahiplenir | Agent'a otomatik atanmaz | İnsan/principal kararı, imzalı standart |

**Kural:** Agent en fazla `expert` olabilir. `authority` insan/principal içindir;
`critical` işlerde son karar insandır.

## Seviye kriterleri

### `aware`

- İlgili capability'nin sözlüğünü, sınırlarını ve tipik hatalarını bilir.
- Verilen checklist'i uygular; çıktısı mutlaka review edilir.
- Kendi başına gate/verdict üretmez.
- Kanıt: kısa not, checklist işareti, reviewer referansı.

### `practitioner`

- Standart durumda **bağımsız** uygular; sapmayı fark ederse durur.
- Test/kanıt yazar; `behavior` gate'ini geçer.
- En az bir reviewer onayıyla leaf kapatabilir.
- Kanıt: çalışan test, evidence comment, küçük ve geri alınabilir diff.

### `expert`

- Uç durumları, hata modlarını ve tradeoff'ları **tasarlar**.
- NFR ve sınır kararlarını gerekçelendirir (ADR/`AR-*`).
- Başka bir agent'ın çıktısını review edebilir; iki bağımsız onaydan biridir.
- Kanıt: ADR, edge-case testi, iki reviewer/architect onayı, maliyet/risk analizi.

### `authority`

- Capability standardını ve kabul eşiğini belirler.
- Çakışan expert görüşlerini çözer; kurumsal riski sahiplenir.
- Yalnız insan/principal tarafından, gerekçeli olarak atanır.
- Kanıt: imzalı standart, karar kaydı, risk kabulü.

## Rol bazında uzmanlık kriterleri

Aşağıdaki maddeler `expert` seviyesinin **asgari** kanıtıdır; `practitioner`
bunların standart alt kümesini yapar.

### Architect

- Sınırları (boundary), veri akışını ve NFR'leri çizer; ADR yazar.
- En az iki alternatifi tradeoff'la karşılaştırır; geri dönüş planı koyar.
- CP DAG ve `depends_on`'u risk ile hizalar.
- Kanıt: `ADR-*`, `AR-*` bulguları, boundary diff review, NFR listesi.

### Analist

- Belirsiz intent'i test edilebilir AC'ye çevirir; out-of-scope yazar.
- AC ↔ test ↔ evidence izlenebilirliğini kurar.
- Kapsam gap'ini follow-up issue'ya dönüştürür.
- Kanıt: AC tablosu, `scope_gap`, traceability matrisi.

### Designer

- Platform kuralını (HIG/Material/WCAG) bilinçli uygular; state matrisi çıkarır.
- Empty/loading/error/offline ve erişilebilirlik durumlarını tasarlar.
- Handoff'ta ölçü, asset, copy ve etkileşim notu verir.
- Kanıt: screenshot, token/design system bağı, a11y notu, state matrisi.

### Developer

- Platform playbook'una uygun, minimal ve geri alınabilir diff üretir.
- Testi önce kırmızı görür; hata/edge case'i kodda temsil eder.
- Sınır ihlali veya kapsam kayması gördüğünde durur.
- Kanıt: kırmızı→yeşil test, lint/typecheck, migration/rollback notu.

### Tester

- Risk tabanlı test stratejisi kurar: sınır, eşdeğerlik, hata yolu, regresyon.
- Flaky testi karantinaya alır; kapsamı AC üzerinden ölçer.
- Adversarial review'da bağımsız ikinci görüş verir.
- Kanıt: test matrisi, `ADV-*`, regression seti, failure injection.

### DevOps

- CI/CD, environment, secret, rollback ve gözlemlenebilirliği birlikte tasarlar.
- Deploy'u kademeli ve geri alınabilir yapar; SLO/alarm tanımlar.
- Maliyet ve kapasite etkisini ölçer.
- Kanıt: pipeline diff, preview/prod planı, SLO, rollback tatbikatı.

### Security

- Trust boundary ve veri akışından tehdit modeli çıkarır.
- Authz matrisi, secret, tedarik zinciri ve kötüye kullanım senaryosunu inceler.
- Bulguyu severity + kanıt + öneri ile yazar; fix'i kendisi kapatmaz.
- Kanıt: `SEC-*`, threat model, SAST/dependency audit, authz testi.

### Data

- İleri/geri migration, backfill ve idempotency planı yazar.
- Veri kaybı, kilit, süre ve rollback riskini ölçer.
- Analitik event sözleşmesini ve retention'ı tanımlar.
- Kanıt: `DM-*`, migration dry-run, rollback provası, veri doğrulama.

### Release

- Versiyon, changelog, store metadata ve privacy/fiyat bütünlüğünü kontrol eder.
- Go/no-go ve kademeli rollout/rollback planı üretir.
- İnsan store kapısına tek karar sorusu ve kanıt paketi bırakır.
- Kanıt: `REL-*`, checklist, store taslağı, rollout planı.

### Marketing / Stores

- ASO, görsel spec, metadata limiti ve inceleme kurallarını bilir.
- Store metnini ürün ve hukuk sınırlarıyla hizalar.
- Kanıt: metadata taslağı, screenshot seti, privacy label kontrolü.

### Marketing / Landing

- SEO, içerik, analytics ve CWV'yi birlikte tasarlar.
- Dönüşüm hipotezini ölçülebilir event'e bağlar.
- Kanıt: landing audit, event şeması, CWV raporu.

### Growth / Run

- Deney tasarımı, sample size, guardrail metrik ve erken durdurma kuralı yazar.
- Readout'u karar önerisine çevirir.
- Kanıt: experiment brief, guardrail panosu, karar notu.

### Documenter

- Doğru doküman tipini seçer (README/ADR/runbook/API/changelog).
- Kod değişiminin hangi dokümanı etkilediğini izler.
- Kanıt: doküman diff'i, link kontrolü, tazelik notu.

### Orchestrator

- Risk, bağımlılık ve kapasiteye göre sıra kurar; WIP'i sınırlar.
- Kapılar arası çelişkiyi görünür kılar; insan kapısını zorlamaz.
- Kanıt: `delivery_path`, kuyruk gerekçesi, bütçe/closure metrikleri.

## Risk ve seviye eşleşmesi

`registry.yaml` içindeki `risk_requirements` asgari seviyeyi belirler;
capability'nin rol seviyesi bunun altına inemez.

| Risk | Asgari | Onaylayan roller | İnsan |
|------|--------|------------------|-------|
| `low` | practitioner | tester | yok |
| `medium` | practitioner | tester | bütçe aşılırsa |
| `high` | expert | architect, tester, security | leaf QA |
| `critical` | expert | architect, tester, security, release | her zaman, 2 insan |

**Etkin seviye = max(capability.role_level, risk.minimum).**
Agent'ın seviyesi etkin seviyenin altındaysa `capability_gap` açılır; `high` ve
`critical` işler gap kapanmadan yürümez.

## Terfi ve düşüş

- **Terfi** kanıtla olur: en az iki başarılı leaf, bir review, bir edge-case
  kanıtı. Terfi `learning` issue'sunda kayıt altına alınır.
- **Düşüş** tetikleri: aynı capability'de tekrarlayan gate fail'i, geri alınan
  karar, güncelliğini yitirmiş playbook veya insan review'inde güven kaybı.
- Seviye düşüşü bir ceza değil, **doğru eşleşme**dir; leaf yeniden planlanır.

## Anti-pattern'ler

| Anti-pattern | Neden yanlış |
|--------------|--------------|
| "Herkes her şeyi bilir" | Seviye anlamsızlaşır; gate kanıtsız kalır |
| Platform başına ayrı rol ID'si | Etiket/kuyruk/evidence çoğalır; varyant kullan |
| Seviyeyi yalnızca kıdemle atamak | Kanıt yok; review yanlılığı |
| Her capability'ye pack uydurmak | Pack şişer; gate ve kanıt yeterli olabilir |
| `authority`'yi agent'a vermek | İnsan kapısı ihlali |
