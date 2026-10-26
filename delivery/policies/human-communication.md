# İnsan iletişimi (zorunlu)

Kullanıcıya (ürün sahibi) yönelik **tüm** sorular, onaylar ve `ask` metinleri bu
kurallara uyar.

## Dil ve ton

- **Türkçe** (kullanıcı Türkçe konuşuyorsa); teknik jargon kullanma.
- Yasak: checkpoint, gate, surface, idempotent, dispatch, YAML, orchestration,
  worktree (yerine "ayrı çalışma kopyası" veya hiç bahsetme).
- İzinli: "ödül", "landing sayfası", "aynı gün iki kez", "onaylıyor musun?".

## Soru formatı

- En fazla **2 cümle**.
- Mümkünse **2–4 net seçenek**; seçenekler de insan dilinde.
- Açık uç tek soru: "Başka bir şey eklemek ister misin?"

| Kötü | İyi |
|------|-----|
| CP-2 için idempotency key UTC mi? | Aynı gün ikinci kez ödül alınsın mı, yoksa gün gece yarısı sıfırlansın mı? |
| UI gate prototype state eşleşmedi | Tasarımdaki boş form ile uygulamadaki ekran aynı görünmüyor; önce tasarımı mı güncelleyelim, uygulamayı mı? |
| agent-approved sonrası dispatch? | Planı onayladın; uygulamanın başlamasını ister misin? |

## Teknik detay nereye gider

- Issue body içindeki `demir-kit` YAML bloğu.
- Orca task spec (worker'a verilen talimat); kullanıcıya okutulmaz.
- `gh issue comment` teknik özet; mühür özeti kullanıcı dilinde issue üstünde kalır.

## Issue ve kod

- Epic kapsamı (`scope-confirmed`) olmadan issue create yok.
- Leaf `agent-approved` olmadan kaynak değişmez.
- Kullanıcıya: "Şimdi sadece kapsamı netleştiriyoruz; uygulama mühürden sonra."

## Kim uygular

- `work-package` (seal), amend, epic intake
- Orca coordinator (`ask`, `gate-create` soru metni)
- Worker önce coordinator'a insan dilinde özet + seçenek verir; kullanıcıya doğrudan
  teknik soru sormaz
