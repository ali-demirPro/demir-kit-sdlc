# İnsan iletişimi (zorunlu)

Kullanıcıya (ürün sahibi) yönelik **tüm** sorular, onaylar ve `orca orchestration ask` metinleri bu kurallara uyar.

## Dil ve ton

- **Türkçe** (kullanıcı Türkçe konuşuyorsa) veya kullanıcının dili; teknik jargon kullanma.
- Yasak kullanıcıya söylemek: checkpoint, gate, surface, idempotent, dispatch, YAML, orchestration, worktree (yerine “ayrı çalışma kopyası” veya hiç bahsetme).
- İzin verilen: “ödül”, “landing sayfası”, “aynı gün iki kez”, “onaylıyor musun?”.

## Soru formatı

- En fazla **2 cümle** soru.
- Mümkünse **2–4 net seçenek** (`orca orchestration ask --options "A,B,C"` — seçenekler de insan dili).
- Açık uç tek soru: “Başka bir şey eklemek ister misin?”

## Örnekler

| Kötü | İyi |
|------|-----|
| CP-2 için idempotency key UTC mi? | Aynı gün ikinci kez ödül alınsın mı, yoksa gün gece yarısı sıfırlansın mı? |
| UI gate için prototype state eşleşmedi | Tasarımdaki boş form ile uygulamadaki ekran aynı görünmüyor; önce tasarımı mı güncelleyelim, uygulamayı mı? |
| agent-approved sonrası dispatch? | Planı onayladın; agent’ların kodu yazmaya başlamasını ister misin? |

## Teknik detay nereye gider

- Issue body içindeki ` ```yaml demir-kit ` bloğu.
- Orca **task spec** (worker’a verilen talimat); kullanıcıya okutulmaz.
- `gh issue comment` teknik özet için; mühür özeti kullanıcı dilinde issue üstünde kalır.

## Issue ve kod (zorunlu)

- **kit-feature:** Kapsam tablosu onaylanmadan `gh issue create` yok. “Basla” = issue aç (onaylıysa), **kod yazma** değil.
- **kit-build:** Hangi **#N** mühürlenecek net olmalı; mühür sonrası uygulama.
- Kullanıcıya: “Şimdi sadece kapsamı netleştiriyoruz; kod kit-build sonrası.”

## Kim uygular

- `work-package` / `work-package-amend` skill’leri
- **kit-feature** / scope-triage (F0–F4)
- Orca **coordinator** (`ask`, `gate-create` soru metni)
- **Worker** önce coordinator’a insan dilinde özet + seçenek; kullanıcıya doğrudan teknik soru sormaz (coordinator `ask` ile)
