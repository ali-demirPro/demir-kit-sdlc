# Capability Matrix

Amaç: **rol kimliğini sabit tutup**, rolün projeye göre hangi yetenekte, hangi
derinlikte ve hangi kanıtla çalışacağını tanımlamak. Web-only projede mobil
yetenekler pasif kalır; iOS projesinde designer HIG ile, Android'de Material ile
konuşur.

## Üç katman

| Katman | Dosya | Ne yapar |
|--------|-------|----------|
| **Capability** | `registry.yaml` | Projede ne var? Platform/domain/distribution/quality + risk tabanı + pack + kanıt |
| **Level** | `levels.md` | Hangi derinlik? `aware` → `practitioner` → `expert` → `authority` |
| **Role profile** | `role-matrix.yaml` | Rol hangi yetenekte hangi seviyede? Odak ve kanıtı ne? |

Variant davranışı (`designer/ios.md`, `tester/web.md`) ayrı leaf'lerde eklenir;
bu dosyalar **ne** ve **ne kadar** sorusunu yanıtlar, **nasıl** sorusunu değil.

## Çözümleme kuralı

```
aktif capability = proje fingerprint'i ∪ ecosystem surfaces ∪ leaf surfaces
gerekli roller  = capability.roles
etkin seviye    = max(capability.roles[rol], risk.minimum)
aktif variant   = rol × aktif capability
pasif           = capability yoksa rol/variant yüklenmez
```

- Bir yüzey eşleşmiyorsa o capability **pasiftir**: dokümanı yüklenmez,
  gate'i istenmez, pack'i zorunlu olmaz, risk tabanını yükseltmez.
- `high`/`critical` işte rolün seviyesi `expert` altındaysa `capability_gap`
  açılır; gap kapanmadan leaf yürümez.
- `authority` yalnız insan/principal içindir; agent en fazla `expert` olur.

## Risk ve seviye

| Risk | Asgari | Onaylayan | İnsan |
|------|--------|-----------|-------|
| low | practitioner | tester | yok |
| medium | practitioner | tester | bütçe |
| high | expert | architect, tester, security | leaf QA |
| critical | expert | architect, tester, security, release | her zaman, 2 insan |

Capability'nin `risk_floor`'u seal riskini **yükseltebilir**, düşüremez.
Örnek: `domain.payments` → `high`, `distribution.app_store` → `critical`.

## Taksonomi

### Platform
`platform.web`, `platform.ios`, `platform.android`, `platform.api`, `platform.cli`

### Domain
`domain.auth`, `domain.payments`, `domain.data`, `domain.analytics`,
`domain.offline`, `domain.i18n`

### Distribution
`distribution.app_store`, `distribution.play`, `distribution.web`

### Quality
`quality.security`, `quality.privacy`, `quality.a11y`,
`quality.performance`, `quality.observability`

## Yeni capability ekleme

1. `registry.yaml`'a `kind.label.description` yaz.
2. `match` alanını gerçek sinyalle doldur (platform/stack/surface/distribution/keyword).
3. `roles` altında **her zorunlu rolün** seviyesini yaz.
4. `packs`, `risk_floor`, `gates`, `evidence` alanlarını doldur.
5. `role-matrix.yaml`'da ilgili rollerin override'larını güncelle.
6. `python3 delivery/scripts/capabilities.py --list` ve `doctor --strict` çalıştır.
7. Test: `delivery/tests/test_capabilities.py`.

**Kural:** capability en az bir rol, bir gate ve bir kanıt taşımıyorsa etiket
değil, gürültüdür.

## Rol matrisi örneği

```yaml
architect:
  default_level: aware
  capabilities:
    platform.ios: expert
    domain.auth: expert
    quality.security: expert
```

`default_level` listelenmeyen capability'ler için geçerlidir. `expert` bir rol
için "uç durum + tradeoff + review" kanıtı ister; detay `levels.md`.

## Proje örnekleri

| Proje | Aktif | Pasif |
|-------|-------|-------|
| Web-only SaaS | platform.web, domain.auth, quality.security | platform.ios/android, distribution.app_store/play |
| iOS uygulaması | platform.ios, distribution.app_store, quality.a11y | platform.web, distribution.play |
| Web + iOS | platform.web, platform.ios, distribution.web, distribution.app_store | platform.android, distribution.play |
| API-only | platform.api, domain.data, quality.security | platform.web/ios/android, distribution.* |

Pasiflik dört katmanda uygulanır: context (doküman yüklenmez), gate (istenmez),
pack (zorunlu olmaz), risk (taban yükselmez).

## Sınırlar

- Bu katman **proje resolver'ı değildir**; fingerprint ve `brief` entegrasyonu
  #55'tedir.
- Variant davranış dosyaları #52–#54'tedir.
- `authority` agent'a atanmaz; insan kapısıdır.
- Capability sayısı 30'u geçerse alt capability'lere böl; rol × platform
  çarpımıyla patlama yaratma.
