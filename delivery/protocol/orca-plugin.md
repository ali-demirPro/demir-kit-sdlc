# Orca plugin (salt-okunur)

demir-kit'in Orca yüzeyi: sağ kenar çubuğunda portföy paneli ve iki durum
çubuğu öğesi. Eklenti kendi kodunu Orca'nın ayrı Node sürecinde çalıştırır;
`delivery/scripts/status.py` sözleşmesini okur, hiçbir şeyi değiştirmez.

## Ne yapar

| Yüzey | Ne gösterir |
|-------|-------------|
| Panel `portfolio` | Proje adı, `source` (`live`/`cache`), `stale`; epic tablosu |
| Durum çubuğu `epic` | İlk epic, checkpoint ilerlemesi, gate sonucu |
| Durum çubuğu `cost` | Maliyet; `status.py` henüz `null` döndüğü için `-` |

Her satır bir epic: `#number`, `durum`, `CP done/total`, `gate`
(`-`/`pass`/`fail`), `risk` (`-` ya da seviye). Panel açılışta sorar, 30
saniyede bir yenilenir; "Yenile" düğmesi anında tazeler.

Veri `python3 <proje>/delivery/scripts/status.py --json` çıktısıdır; işçi
(`src/worker.ts`) sonucu 30 saniye `orca.storage` içinde tutar. Sözleşme
alanları [status.md](status.md), panel-işçi tipleri
`plugins/orca/src/protocol.ts`. Yüklemede derleme yoktur: Orca `.ts`/`.tsx`
dosyalarını kendisi çevirir.

## Kurulum

Geliştirme klasörü olarak yükle:

```bash
orca plugin dev load plugins/orca --approve <fingerprint>
```

Komut parmak izini kendisi yazar; onaysız çalıştırıldığında
`approval_required` ve `--approve <fingerprint>` satırını döner. Alternatif:
**Settings → Plugins → Development folders**. Klasör epic worktree'sinde de
olabilir; yol mutlak verilmelidir. Proje yolu **Ayarlar → demir-kit → Proje
yolu** (`settings.projectPath`) ile verilir; boşsa `kit.config.yaml` içeren ilk
workspace kullanılır ve yol değişince durum anında yenilenir.

Doğrula:

```bash
orca plugin check plugins/orca     # iki senaryo: fresh, empty
orca plugin inspect plugins/orca   # katkılar, izinler, içerik özeti
python3 -m unittest delivery.tests.test_orca_plugin
```

## İzinler

Manifest `execution: trusted-worker` ve üç yetenek ister:

| Yetenek | Neden |
|---------|-------|
| `workspace:read` | `workspace.list` ile proje kökünü bulmak |
| `storage:own` | 30 saniyelik durum önbelleği |
| `settings:own` | `projectPath` ayarını okumak |

`trusted-worker` eklentinin kodunu **kullanıcı hesabının yetkileriyle**, Orca
kum havuzunun dışında çalıştırır: yalnız kendi kodunu yükle. Aynı süreç
`status.py`'yi `execFile` ile çağırır; kabuk kullanmaz.

## Sınırlar

- Salt-okunur: issue, etiket, worktree, dosya veya git durumu yazılmaz.
- `transition`, `claim`, `seal`, `update.py` çağrılmaz; mutasyon aracı yoktur.
- Repoya yazma yok: `writeFile`, `mkdir`, `appendFile` kullanılmaz. Kalıcı veri
  yalnızca Orca'nın `storage` ve `settings` API'lerinde durur.
- Durum çubuğu güncellenemezse (başsız ana makine) panel yine çalışır; hata
  yalnızca eklenti günlüğüne düşer. Bu sınırları
  `delivery/tests/test_orca_plugin.py` içindeki `ReadOnlyTests` denetler.

## Sürüm

Durum çubuğu katkısı resmi olarak Orca `>= 1.4.248` ister (`engines.orca`).
Orca 1.4.247'de de panel ve durum çubuğu öğeleri görünür; eksik yüzey hata değildir.

## Sorun giderme

| Belirti | Komut |
|---------|-------|
| Panel boş / "demir-kit bulunamadı" | `orca plugin logs local.demir-kit`; `projectPath` ayarını kontrol et |
| Durum eski görünüyor | `orca plugin restart local.demir-kit`, sonra "Yenile" |
| Paneli gözle kontrol | `orca plugin shot local.demir-kit --panel portfolio` |
| İşçiyi panel gibi çağır | `orca plugin dev request plugins/orca status.snapshot` |

Günlükte `status.snapshot` hatası varsa önce proje kökünde
`python3 delivery/scripts/status.py --json` çalıştır: sorun eklentide değil,
`status.py` ya da `gh` oturumundadır.
