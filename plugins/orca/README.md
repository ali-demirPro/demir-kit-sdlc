# demir-kit

Orca sağ kenar çubuğu paneli (`src/panel.tsx`) ve eklentinin kendi işçisi
(`src/worker.ts`). Panel `plugin.request('status.snapshot')` ile sorar; işçi
`<proje>/delivery/scripts/status.py --json` çalıştırır, sonucu 30 saniye
`orca.storage` içinde tutar ve durum çubuğunu günceller. `src/protocol.ts` iki
tarafın sözleşmesini tanımlar. Orca iki dosyayı da yüklerken derler: derleme
adımı yok.

Proje yolu `Ayarlar > demir-kit > Proje yolu` ile verilir; boşsa `kit.config.yaml`
içeren ilk workspace kullanılır. Bu sürüm yalnız okur: claim, transition veya
seal çağırmaz ve repoya yazmaz.

```sh
orca plugin validate .
orca plugin inspect .
```

Orca yayıncıyı eklentinin kurulduğu yerden türetir: depo sahibi ya da klasör
için `local`. Ayrıntılar:
https://github.com/stablyai/orca/blob/main/docs/reference/plugin-authoring.md.
