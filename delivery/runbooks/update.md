# Güncelleme — tek komut

`self_update.py` projedeki kiti günceller. Varsayılan yalnız plandır; ağa
çıkmaz, dosya yazmaz. Yazmak için `--apply` verilir.

## Dry-run (önerilen ilk adım)

```bash
./delivery/scripts/self_update.py --project . --json
```

Çıktı: `ok`, `project`, `kit_root`, `mode` (`self`, `submodule` ya da
`vendored`), `version`, `upstream` ve `steps[]` (`{name, command}`; iç işlemler
`{name, internal}`). Komutlar argv listesidir; shell yoktur.

`mode` tahmin edilmez; sırayla bakılır:

1. `self` — `kit.root` projeyi gösteriyorsa **ve** `git -C <proje> remote
   get-url origin` çıktısı `kit.upstream.git` ile aynıysa (sondaki `/` ve `.git`
   yok sayılır).
2. `submodule` — kit kökünde `.git` varsa (dosya ya da dizin) **ya da** yol
   `.gitmodules` içinde submodule olarak tanımlıysa. Henüz
   `submodule update --init` çalışmamış kit de bu moda girer; `vendored`'a
   düşmez.
3. `vendored` — diğer her durum.

`kit.root: "."` tek başına `self` yapmaz.

```json
{
  "ok": true,
  "project": "/work/product",
  "kit_root": "/work/product/demir-kit",
  "mode": "vendored",
  "version": "2.57.0",
  "upstream": "https://github.com/ali-demirPro/demir-kit-sdlc.git",
  "steps": [
    {"name": "clone", "command": ["git", "clone", "--depth", "1", "--branch", "main", "--", "https://github.com/ali-demirPro/demir-kit-sdlc.git", "/home/me/.cache/demir-kit/upstream"]},
    {"name": "vendor_sync", "command": ["python3", "/home/me/.cache/demir-kit/upstream/delivery/scripts/vendor_sync.py", "--source", "/home/me/.cache/demir-kit/upstream", "--target", "/work/product", "--apply"]},
    {"name": "skills", "command": ["bash", "/home/me/.cache/demir-kit/upstream/install.sh"]},
    {"name": "doctor", "command": ["/work/product/demir-kit/delivery/scripts/doctor.sh", "--product", "--root", "/work/product"]}
  ]
}
```

## Uygula

```bash
./delivery/scripts/self_update.py --project . --apply
```

Adımlar sırayla çalışır; her adım `{name, command, exit_code, ok}` döner ve ilk
hatada durur (`ok:false`, exit 1). `--json` ile makine okunur çıktı alınır.

| Mod | Ne yapar |
|-----|----------|
| `self` | Kit kökü projenin kendisi: `git pull --ff-only`, sonra `doctor.sh` |
| `submodule` | Submodule pointer'ını `--remote` ile ilerletir, config sürümünü yazar, `doctor.sh --product` |
| `vendored` | Önbelleği klonlar/tazeler, `vendor_sync --apply`, skill kurulumu, `doctor.sh --product` |

Önbellek `~/.cache/demir-kit/upstream`; `--cache-dir` ile değiştirilir.
`--ref` dalı seçer (varsayılan `main`); submodule modunda verilirse o commit'e
sabitler. `--source` yerel bir kit kökü verir: klon/fetch atlanır, doğrudan o
dizinden senkronlanır.

### Plan hataları (`ok:false`)

Plan aşamasında hiçbir şey yazılmaz; hata `--json` ile `ok:false` ve `error`
olarak döner, çıkış kodu 1'dir.

| Durum | Mesaj |
|-------|-------|
| `kit.upstream.git` yok (vendored, `--source` yok) | `kit.upstream.git yok` |
| Değer `-` ile başlıyor | `kit.upstream.git '-' ile başlayamaz` |
| Değer desteklenmeyen biçimde | `kit.upstream.git desteklenmeyen biçim` |
| Önbellek dizini var ama git deposu değil | `önbellek bir git deposu değil: <yol>` |
| `--ref` boş | `--ref boş olamaz` |
| `--ref` boşluk içeriyor / `-` ile başlıyor / `..` içeriyor | `--ref boşluk içeremez`, `--ref '-' ile başlayamaz`, `--ref '..' içeremez` |
| `--ref` refspec karakteri içeriyor (`:`, `*`, `^`, `~`, `@`, ters bölü) | `--ref refspec karakteri içeremez` |

Kabul edilen upstream biçimleri: `https://`, `http://`, `git@`, `ssh://`,
`file://` ve `/` ile başlayan yerel yollar. Git komutlarında upstream her zaman
`--` sonrasında verilir (`git clone … -- <upstream> <dizin>`), böylece değer
seçenek gibi yorumlanmaz. Önbellek git deposu değilse sessizce clone denenmez;
dizini silin ya da `--cache-dir` ile başka bir yol verin.

### Submodule modu

Kit, ürün reposunda git submodule olarak duruyorsa (`kit.root: demir-kit` ve
`demir-kit/.git` dosyası/dizini varsa ya da yol `.gitmodules` içinde
tanımlıysa) plan şu sırayı üretir:

```bash
./delivery/scripts/self_update.py --project . --json
```

```json
{
  "ok": true,
  "project": "/work/product",
  "kit_root": "/work/product/demir-kit",
  "mode": "submodule",
  "version": "2.58.0",
  "steps": [
    {"name": "submodule", "command": ["git", "-C", "/work/product", "submodule", "update", "--init", "--remote", "--", "demir-kit"]},
    {"name": "config", "internal": "config"},
    {"name": "doctor", "command": ["/work/product/demir-kit/delivery/scripts/doctor.sh", "--product", "--root", "/work/product"]}
  ]
}
```

- `submodule` — `git submodule update --init [--remote] -- <göreli yol>`; yol
  `--` sonrasında verilir. `--remote` yalnız `--ref` verilmediğinde kullanılır;
  `--ref` varsa init kayıtlı commit'e getirir, ağ ikinci kez fetch'te harcanır.
- `fetch` + `checkout` — yalnız `--ref` verildiğinde:
  `git -C <kit_root> fetch --depth 1 origin -- <ref>` ve
  `git -C <kit_root> checkout --detach FETCH_HEAD`.
- `config` — `kit.config.yaml` içindeki `kit.version` satırını
  `kit_root/VERSION` ile eşitler; satır yoksa `kit:` bloğuna ekler. Dosya
  yeniden yazılmaz: yorumlar, sıra ve CRLF satır sonları korunur. Kabuk komutu
  değildir, `--apply` sırasında iç işlem olarak
  `{name: "config", exit_code: 0}` döner.
- `doctor` — `doctor.sh --product --root <proje>`.

`--apply` **commit atmaz**. Submodule güncellemesi ürün reposunda yalnız pointer
değişikliği bırakır; mesaj `pointer değişti; ürün reposunda commit'le` olur.
Değişikliği normal akışınızla (inceleme + commit) ürün reposuna yazın.

```bash
./delivery/scripts/self_update.py --project . --apply
git -C <proje> add demir-kit kit.config.yaml
git -C <proje> commit -m "chore(kit): demir-kit 2.58.0"
```

### Skill adımı (yalnız vendored)

`skills` adımı `install.sh`'ı çalıştırır ve skill'leri **kit ağacının dışına**
yazar: normalde proje dizinindeki skill klasörüne, `--with-platform`
kullanıldığında ayrıca **global** kullanıcı dizinine (`~/.agents/skills`,
`~/.claude/skills` sembolik linkleri). `git restore` bu adımı geri almaz.
Skill kurulumunu atlamak için:

```bash
./delivery/scripts/self_update.py --project . --apply --skip-skills
```

## Geri dönüş

```bash
# Vendored modda kit kopyası ve config'i geri al
git -C <proje> restore demir-kit kit.config.yaml

# Self modda son iyi commit'e dön
git -C <proje> reset --hard <son-iyi-sha>

# Submodule modda eski commit'e dön ve pointer'ı geri al
git -C <proje>/demir-kit checkout <eski-sha>
git -C <proje> submodule update --init -- demir-kit
git -C <proje> restore kit.config.yaml

# Skill adımı git dışında yazar: eski sürümün install.sh'ını aynı dizinde
# tekrar çalıştırın; global kopya kaldıysa silin
(cd <proje> && bash <eski-kit>/install.sh)
rm -rf ~/.agents/skills/<skill> ~/.claude/skills/<skill>

# Durumu gör (yazmaz)
./delivery/scripts/self_update.py --project . --json
./delivery/scripts/doctor.sh --product --root <proje>
```

Sorun sürerse son iyi commit'e dönüp `kit.config.yaml` sürümünü sabitleyin;
`doctor.sh --product --root <proje>` tekrar yeşil olmalı. Submodule modunda
`--apply` commit atmadığı için geri dönüş yalnız pointer revert'idir:
`git -C <proje> submodule update --init -- demir-kit` ve
`git -C <proje> checkout -- kit.config.yaml`.
