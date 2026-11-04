# Orca plugin

demir-kit'in Orca yüzeyi: sağ kenar çubuğunda portföy paneli ve iki durum
çubuğu öğesi. Eklenti kendi kodunu Orca'nın ayrı Node sürecinde çalıştırır;
`delivery/scripts/status.py` sözleşmesini okur. Panelden gelen kabul ve claim
istekleri yalnız kit scriptleriyle (`transition.sh`, `next-leaf.sh`) yürür; red
yalnız `decision: rejected` yorumu yazar. Başarılı kabul geçişinden sonra issue
`gh issue close N --reason completed` ile kapanır. Panel repoya dosya yazmaz.

## Ne yapar

| Yüzey | Ne gösterir |
|-------|-------------|
| Panel `portfolio` | Liste: her repo için tek proje kartı, epic ve leaf satırları. Detay: seçilen epic tam panelde, düz özet ve aksiyonlar |
| Durum çubuğu `epic` | Odaklı proje `ok` ve aktif epiği varsa `EP-N · CP d/t · gate g`; yoksa sağlıklı proje sayısı `N proje` |
| Durum çubuğu `cost` | Maliyet; `status.py` henüz `null` döndüğü için `-` |

Her proje kartı repo adını (`project.tracker.repo`, yoksa proje adı) başlık yapar;
yanında kısa yol ve aktif iş sayısı `epic N · leaf M` rozeti durur. Sayılar
`status.py`'den geldiği gibidir: kapalı epic'ler sayılmaz. Hiç aktif epiği
olmayan proje kartı gizlenmez, "açık iş yok" satırı gösterir. Her kart bir epic
listesi çizer: satır `#number — başlık`, altında o epic'in leaf satırları
`#number — başlık · durum` (`leaf-done`, `executing`, `agent-approved`, `intake`,
`open`/`closed`). Epic satırında durum (`executing`, `blocked`, `leaf-done` …),
`CP done/total`, `gate` (`-`/`pass`/`fail`) ve `risk` rozetleri vardır. Bir leaf
satırına tıklama, panele değil işçiye `plugin.request("workspace.open", {id})`
gönderir; `workspace.open`'ı `workspace:write` yetkisiyle yalnız işçi çağırır ve
`{ok}` (hata: `{ok:false,error}`) döner. Panel açılışta sorar, 30 saniyede bir
yenilenir; "Yenile" düğmesi anında tazeler.

## İki görünüm

Panel tek bir `view` durumu taşır: `{kind:'list'}` ya da
`{kind:'detail', projectId, epicNumber}`. Liste görünümünde her proje kartı
epic ve leaf satırlarını çizer; epic satırına tıklama aynı paneli düz detaya
çevirir, "‹ Geri" listeye döner. Görünüm `plugin` kapsamında saklanır.

Detay **düzdür**, iç içe liste yoktur: başlık `#n — title`, state rozeti,
`CP done/total`, `ajan onayı` ve `insan QA` rozetleri, `next_action`, kısa
`updated_at` (`04.11 10:00`) ve aksiyon satırı. Detayda leaf listesi
gösterilmez; leaf satırları yalnız liste görünümünde kalır. Detayda
`checkpoints[]` satırları `#<leaf> · CP-1 ✓ başlık` / `#<leaf> · CP-2 ○ başlık`
olarak CP özetiyle birlikte durur. Eski `status.py` biçimi (`checkpoints` dizi
değil `{done,total}`) çökmez: CP listesi boş kalır, rozet `0/0` olur. "Issue'yu
aç" düğmesi `epics[].url` adresini `shell.openExternal` ile tarayıcıda açar;
URL `status.py`'den gelir (`tracker.repo` yoksa `null`, düğme çizilmez).

## Aksiyonlar

Panel aksiyonu yalnız işçiye istek olarak gider; istek `projectPath` taşır ve
işçi projeyi son anlık görüntüdeki `path` ile eşleştirir (eşleşme yoksa
`{ok:false}`). İşçi komutu çalıştırır ve `{ok, message, exitCode, tail, url}`
döner. Hata fırlatılmaz: başarısız komut `ok:false`, son satırlar (`tail`) ve
issue bağlantısı (`url`) ile panele döner; panel çalışmaya devam eder ve
başarısız aksiyonda `tail` ile "Issue'yu aç" düğmesini gösterir.

| İstek | Ne yapar |
|-------|----------|
| `epic.decision {projectPath, issue, decision}` | Önce `gh issue view N --json labels` ile `human-qa` etiketi aranır; yoksa hiçbir şey yazılmaz. Sonra `gh api user --jq .login` ile kullanıcı bulunur; `accepted` ise geçici dosyaya `demir-kit-accept` YAML bloğu (`epic`, `decision: accepted`, `by`) yazılıp `gh issue comment --body-file` ile yorumlanır, ardından `transition.sh --issue N --to epic-done --accept <login>` çağrılır. Geçiş düşerse az önce yazılan yorum `gh api -X DELETE repos/<repo>/issues/comments/<id>` ile silinir; `<id>` yorum URL'sindeki `#issuecomment-<id>`'den alınır. Geçiş başarılıysa issue `gh issue close N --reason completed` ile kapatılır: kapatma düşerse geçiş **korunur**, yanıt `{ok:true, warning}` olur ve panel uyarı gösterir. `rejected` ise yalnız `decision: rejected` yorumu yazılır, durum geçişi ve kapatma çağrılmaz |
| `leaf.claim {projectPath}` | Projedeki ilk `agent-approved` leaf hedeflenir; `gh issue view N --json labels` ile `agent-approved` var ve `executing`/`leaf-done` yok denetlenir. Kapı geçerse `next-leaf.sh --claim` çağrılır |

Sunucu tarafı kapı yorumdan öncedir: kabul/red için `human-qa`, claim için
`agent-approved` ve `!(executing|leaf-done)` aranır; etiketler uygun değilse
istek `{ok:false}` döner ve GitHub'a hiçbir şey yazılmaz. Kapı `gh issue view`
çıktısını okuyamazsa da aksiyon durur.

Komutlar projenin dizininde (`cwd`) ve kit kökündeki scriptle çalışır. Yorum
gövdesi `fs.mkdtempSync(join(os.tmpdir(), 'demir-kit-'))` ile açılan 0700 geçici
dizinde, 0600 izinli tek dosyada durur; iş bitince dizin silinir.

Panel epic detayında `human_qa` varsa "Kabul et" / "Reddet", proje kartında
`agent-approved` leaf varsa "Sıradaki leaf'i claim et" düğmesi gösterilir.
Claim leaf satırında değil yalnız proje kartındadır ve istek `{projectPath}`'dir.
Hepsi **iki adımlı onaydır**: ilk tık "Emin misin? Evet/Vazgeç" satırını açar,
ikinci tık isteği çağırır. Başarılı aksiyondan sonra panel liste görünümüne
döner, seçimi temizler ve `status.snapshot`'ı yeniler; başarısız aksiyonda
detay açık kalır, sonuç notu `tail` + issue linkiyle görünür. Başarılı kabulde
issue kapanmazsa not `warning` taşır ve panel uyarı kutusu çizer.

Aksiyon geri alınabilir: kabulde geçiş düşerse yorum silinir; başka bir yanlış
kabulde `epic-done` yerine `epic-reconcile`/`human-qa` etiketleri geri konur.
Red yalnız yorum bırakır, durum değiştirmez; yanlış reddi düzeltmek için iş
yeniden `executing`'e alınır ve yeni bir insan kararı istenir. Panelin kendisi
etiket ya da dosya düzeltmez; düzeltme de aynı kit scriptinden geçer.

## Canlı durum

İşçi `agents.list` (yetenek `agent:read`) ile odaklı workspace'in ajanlarını
okur ve `status.snapshot` içinde proje kartına `agents: [{terminalId,title,state}]`
ve `live: {working,blocked,waiting,idle,done}` ekler. Ajanlar yalnız odaklı
workspace'in kartına yazılır; odaklı workspace kit taşımıyorsa hiçbir karta ajan
yazılmaz (`agents: []`, sıfır sayaçlar). Diğer kartlar da boş liste ve sıfır
sayaç taşır; API yalnız odaklı workspace'i verir. `agent.status.changed` olayı
`workspaceId` taşıyorsa yalnız o workspace'in kartı tazelenir; olay başka bir
workspace'e aitse hiçbir kart değişmez. `idle` durumu da sayılır (`boşta`),
sessizce atılmaz. Ajan okuması hata verirse proje düşmez: `agents: []`, sıfır
sayaçlar ve kısa bir uyarı kalır. Panel kartta `● 2 çalışıyor · 1 boşta · 1
engelli` satırını ve ilk üç ajanın başlığını gösterir.

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
orca plugin check plugins/orca     # dört senaryo: fresh, detail, legacy, empty
orca plugin inspect plugins/orca   # katkılar, izinler, içerik özeti
python3 -m unittest delivery.tests.test_orca_plugin
```

## İzinler

Manifest `execution: trusted-worker` ve beş yetenek ister:

| Yetenek | Neden |
|---------|-------|
| `workspace:read` | `workspace.list` ile proje köklerini bulmak |
| `workspace:write` | Tıklamada `workspace.open` çağırmak (yalnız işçi) |
| `agent:read` | `agents.list` ve `agent.status.changed` ile canlı ajan durumu |
| `storage:own` | 30 saniyelik durum önbelleği |
| `settings:own` | `projectPath` ayarını okumak |

`trusted-worker` eklentinin kodunu **kullanıcı hesabının yetkileriyle**, Orca
kum havuzunun dışında çalıştırır: yalnız kendi kodunu yükle. Aynı süreç
`status.py`'yi `execFile` ile çağırır; kabul ve claim aksiyonlarında kit
scriptlerini `bash` ile çalıştırır, red yalnız yorum yazar. Kullanıcı girdisi
kabuğa geçmez: argümanlar diziyle verilir.

## Sınırlar

- Panel repoya yazmaz: issue, etiket, worktree, dosya veya git durumu doğrudan
  değiştirilmez. Kabul ve claim yalnız kit scriptleriyle yürür; red yalnız
  `decision: rejected` yorumu bırakır.
- Satır tıklaması `plugin.request("workspace.open")` ile işçiye gider; işçi
  `orca.host.call` ile o projenin workspace'ini açar. Bu yöntem Orca'da
  `workspace:write` ister; manifest bu yetkiyi taşır, reddedilirse hata
  `{ok:false,error}` olarak panele döner ve panel çalışmaya devam eder.
- `transition.sh` ve `next-leaf.sh` dışında durum mutasyonu yoktur; doğrudan
  `git commit`, `git push` veya `gh pr merge` çağrılmaz. `seal` ve `update.py`
  panelden çalışmaz. İki yazma istisnası vardır: kabul geçişinden sonra issue
  kapanışı (`gh issue close`), ve kabul geçişi düşünce yazılan yorumun
  `gh api -X DELETE` ile geri alınması.
- Repoya yazma yok: kalıcı veri Orca'nın `storage` ve `settings` API'lerinde
  durur. Yalnız kabul/red yorumu için `os.tmpdir()` altında 0700 geçici dizin
  ve 0600 dosya yazılır, iş bitince dizin silinir; `mkdir`/`appendFile`
  kullanılmaz.
- Durum çubuğu güncellenemezse (başsız ana makine) panel yine çalışır; hata
  yalnızca eklenti günlüğüne düşer. Bu sınırları
  `delivery/tests/test_orca_plugin.py` içindeki `PanelTests`, `ActionTests` ve
  `ReadOnlyTests` denetler.

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
