# Orca plugin (salt-okunur)

demir-kit'in Orca yüzeyi: sağ kenar çubuğunda portföy paneli ve iki durum
çubuğu öğesi. Eklenti kendi kodunu Orca'nın ayrı Node sürecinde çalıştırır;
`delivery/scripts/status.py` sözleşmesini okur, hiçbir şeyi değiştirmez.

## Ne yapar

| Yüzey | Ne gösterir |
|-------|-------------|
| Panel `portfolio` | Her repo için tek proje kartı: repo adı + kısa yol, `epic N · leaf M`; epic ve leaf satırları |
| Durum çubuğu `epic` | Odaklı proje `ok` ve aktif epiği varsa `EP-N · CP d/t · gate g`; yoksa sağlıklı proje sayısı `N proje` |
| Durum çubuğu `cost` | Maliyet; `status.py` henüz `null` döndüğü için `-` |

Her proje kartı repo adını (`project.tracker.repo`, yoksa proje adı) başlık yapar;
yanında kısa yol ve aktif iş sayısı `epic N · leaf M` rozeti durur. Sayılar
`status.py`'den geldiği gibidir: kapalı epic'ler sayılmaz. Hiç aktif epiği
olmayan proje kartı gizlenmez, "açık iş yok" satırı gösterir. Her kart bir epic
listesi çizer: satır `#number — başlık`, altında o epic'in leaf satırları
`#number — başlık · durum` (`leaf-done`, `executing`, `agent-approved`, `intake`,
`open`/`closed`). Epic satırında `CP done/total`, `gate` (`-`/`pass`/`fail`) ve
`risk` rozetleri vardır. Bir epic veya leaf satırına tıklama, panele değil işçiye
`plugin.request("workspace.open", {id})` gönderir; `workspace.open`'ı
`workspace:write` yetkisiyle yalnız işçi çağırır ve `{ok}` (hata: `{ok:false,error}`)
döner. Panel açılışta sorar, 30 saniyede bir yenilenir; "Yenile" düğmesi anında
tazeler.

## Çok proje

İşçi `workspace.list` ile bütün workspace'leri gezer, her biri için `kit.config.yaml`
üzerinden kit kökünü çözer ve `status.py --json` koşar. Aynı repo tek kartta
toplanır: anahtar sırası `status.project.repo_root`, `project.tracker.repo`, son
çare olarak epic worktree son eki (`/epic-<N>`) atılmış normalize yoldur.
`repo_root` git ortak dizininin üst dizinidir; böylece ana checkout ile epic
worktree'si iki ayrı proje gibi görünmez. Aynı anahtar için odaklı workspace,
yoksa worktree olmayan yol (yolunda `/epic-` geçmeyen ana checkout) kalır.
Kartlar odaklı proje önce, sonra ada göre sıralanır; ayarlardaki `projectPath`
odaklıdan sonra gelir. Kit'i olmayan workspace grubu hiç görünmez.

Bir projede `gh`, python ya da `status.py` hatası olursa yalnız o proje `ok: false`
ve `error` ile döner; diğer projeler `ok: true` kalır. Üst düzey `code: "no-kit"`
yalnız hiçbir workspace'te kit yoksa gelir; panel o zaman boş durum çizer.

Önbellek proje başına 30 saniyedir: `orca.storage` anahtarı `project:<yol>`, değeri
`{saved_at, project}`. "Yenile" ve `workspace.changed` bu önbelleği atlar.

Veri `python3 <proje>/delivery/scripts/status.py --json` çıktısıdır. Sözleşme
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

Manifest `execution: trusted-worker` ve dört yetenek ister:

| Yetenek | Neden |
|---------|-------|
| `workspace:read` | `workspace.list` ile proje köklerini bulmak |
| `workspace:write` | Tıklamada `workspace.open` çağırmak (yalnız işçi) |
| `storage:own` | 30 saniyelik durum önbelleği |
| `settings:own` | `projectPath` ayarını okumak |

`trusted-worker` eklentinin kodunu **kullanıcı hesabının yetkileriyle**, Orca
kum havuzunun dışında çalıştırır: yalnız kendi kodunu yükle. Aynı süreç
`status.py`'yi `execFile` ile çağırır; kabuk kullanmaz.

## Sınırlar

- Salt-okunur: issue, etiket, worktree, dosya veya git durumu yazılmaz.
- Satır tıklaması `plugin.request("workspace.open")` ile işçiye gider; işçi
  `orca.host.call` ile o projenin workspace'ini açar. Bu yöntem Orca'da
  `workspace:write` ister; manifest bu yetkiyi taşır, reddedilirse hata
  `{ok:false,error}` olarak panele döner ve panel çalışmaya devam eder.
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
