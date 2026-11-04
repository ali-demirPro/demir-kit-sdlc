# Güncelleme — tek komut

`self_update.py` projedeki kiti günceller. Varsayılan yalnız plandır; ağa
çıkmaz, dosya yazmaz. Yazmak için `--apply` verilir.

## Dry-run (önerilen ilk adım)

```bash
./delivery/scripts/self_update.py --project . --json
```

Çıktı: `ok`, `project`, `kit_root`, `mode` (`self` ya da `vendored`),
`version`, `upstream` ve `steps[]` (`{name, command}`). Komutlar argv listesidir;
shell yoktur.

`mode` tahmin edilmez: `self` yalnız `kit.root` projeyi gösteriyorsa **ve**
`git -C <proje> remote get-url origin` çıktısı `kit.upstream.git` ile aynıysa
(sondaki `/` ve `.git` yok sayılır). Aksi her durum `vendored`'dır;
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
| `vendored` | Önbelleği klonlar/tazeler, `vendor_sync --apply`, skill kurulumu, `doctor.sh --product` |

Önbellek `~/.cache/demir-kit/upstream`; `--cache-dir` ile değiştirilir.
`--ref` dalı seçer (varsayılan `main`). `--source` yerel bir kit kökü verir:
klon/fetch atlanır, doğrudan o dizinden senkronlanır.

### Plan hataları (`ok:false`)

Plan aşamasında hiçbir şey yazılmaz; hata `--json` ile `ok:false` ve `error`
olarak döner, çıkış kodu 1'dir.

| Durum | Mesaj |
|-------|-------|
| `kit.upstream.git` yok (vendored, `--source` yok) | `kit.upstream.git yok` |
| Değer `-` ile başlıyor | `kit.upstream.git '-' ile başlayamaz` |
| Değer desteklenmeyen biçimde | `kit.upstream.git desteklenmeyen biçim` |
| Önbellek dizini var ama git deposu değil | `önbellek bir git deposu değil: <yol>` |

Kabul edilen upstream biçimleri: `https://`, `http://`, `git@`, `ssh://`,
`file://` ve `/` ile başlayan yerel yollar. Git komutlarında upstream her zaman
`--` sonrasında verilir (`git clone … -- <upstream> <dizin>`), böylece değer
seçenek gibi yorumlanmaz. Önbellek git deposu değilse sessizce clone denenmez;
dizini silin ya da `--cache-dir` ile başka bir yol verin.

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

# Skill adımı git dışında yazar: eski sürümün install.sh'ını aynı dizinde
# tekrar çalıştırın; global kopya kaldıysa silin
(cd <proje> && bash <eski-kit>/install.sh)
rm -rf ~/.agents/skills/<skill> ~/.claude/skills/<skill>

# Durumu gör (yazmaz)
./delivery/scripts/self_update.py --project . --json
./delivery/scripts/doctor.sh --product --root <proje>
```

Sorun sürerse son iyi commit'e dönüp `kit.config.yaml` sürümünü sabitleyin;
`doctor.sh --product --root <proje>` tekrar yeşil olmalı.
