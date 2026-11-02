# Model seçimi

Model ve effort **kullanıcıya ve oturuma** aittir. Kit varsayılan olarak
`--model` / `--effort` geçirmez; worker ortamın varsayılan modelini kullanır.
Rol bazlı "ucuz/güçlü model" yönlendirmesi bilinçli olarak yoktur.

## Üç mod

| Mod | Ayar | Davranış |
|-----|------|----------|
| Varsayılan (A) | — | Hiçbir model/effort geçirilmez; oturum/ortam modeli |
| Miras (B) | `orca.inherit_session_model: true` | Koordinatör oturumunun modeli worker'a `--model` olarak verilir |
| Açık override | `orca.allow_model_override: true` + `orca.role_defaults.<rol>.model/effort` | Yalnız bu bayrakla rol bazlı model/effort uygulanır |

- `role` yalnız `agent` taşıyorsa override bayrağı gerekmez (model seçimi değil).
- Miras açıkken oturum modeli okunamazsa worker modelsiz açılır (ortam modeli);
  bu bir hata değildir.
- `opencode2` için `--effort` desteklenmez; effort ayarlanırsa doctor uyarır.

## Koruma

`doctor` (`model policy`) `role_defaults` içinde `model`/`effort` varsa ve
`allow_model_override` true değilse **hata** verir. Böylece farkında olmadan
model dayatılamaz. `inherit_session_model` tek başına override sayılmaz.

## Uygulama

- `delivery/scripts/model_policy.py` — tek karar noktası.
- `orca_plan.role_launch` ve `review_wave` buradan beslenir.
- Varsayılan `kit.config.yaml` boştur; `orca.role_defaults` yazılmaz.

## Done when

`role_launch` varsayılanda boş döner, worker komutunda `--model`/`--effort`
yoktur; miras ve override yalnız açık bayrakla çalışır ve `doctor.sh --strict`
model politikasını denetler.
