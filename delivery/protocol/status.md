# Status

Salt-okunur durum sözleşmesi: proje, kit ve epic'lerin tek komutla özeti.
Komut `python3 delivery/scripts/status.py`; durum dosyası yazmaz (yalnız önbellek).

## CLI

| Argüman | Anlam |
|---------|-------|
| `--project D` | Proje dizini; yoksa `kit.config.yaml` olan üst dizin, yoksa kit kökü |
| `--json` | JSON sözleşmesini yazdır (yoksa kısa metin) |
| `--offline` | Ağa çıkmaz; önbellek varsa ondan, yoksa yerel iskelet döner |
| `--with-gate` | Epic başına `doctor.sh --issue N` koşar |
| `--with-cost` | Maliyet alanı; henüz toplanmıyor (`null`), uyarı verir |
| `--cache-ttl N` | Önbellek ömrü saniye; `0` (varsayılan) önbellek kullanılmaz |
| `--all-epics` | Kapanmış (`epic-done` etiketli ya da kapalı) epic'leri de listeler; varsayılan kapalı |
| `--full` | Rezerve; şimdilik ek alan üretmez |

## Sözleşme

| Alan | Anlam |
|------|-------|
| `contract_version`, `generated_at` | Sözleşme sürümü (şu an `1`) ve UTC ISO-8601 üretim damgası |
| `stale`, `source` | Durum eksik mi; `live` taze, `cache` önbellek |
| `kit` | `version`, `pin` (kısa SHA), `dirty` |
| `project` | `name`, `profile`, `repo_root`, `tracker.provider`, `tracker.repo`; `repo_root` git ortak dizininin üst dizinidir (worktree'de ana checkout), git yoksa `null` |
| `epics[]` | Yalnız aktif epic'ler (`epic-done` etiketi ve kapalı issue hariç; `--all-epics` hepsini verir): `number`, `title`, `state`, `risk`, `checkpoints[]`, `updated_at`, `url`, `leaves[]`, `gate`, `open_findings`, `approvals`, `next_action`, `cycle_minutes`, `cost_delta`, `evaluations` |
| `evaluations` | Proje kökündeki `.kit/evaluations.json` dosyasından salt-okur eval özeti: `batch`, `cases_pass`, `cases_total`, `discovery_rate`, `findings{friction,objection,opportunity}`, `updated_at`. Dosya ya da epic kaydı yoksa tüm alanlar `null`; geçersiz alan yine `null` olur ve `warnings`e kısa Türkçe uyarı düşer. Sıfır uydurulmaz |
| `checkpoints[]` | Epic çocuklarının seal'lerindeki checkpoint'ler, çocuk sırasıyla: `{id, title, done, leaf}`. `done` çocuk bazlıdır: o çocuk `leaf-done` ise `true`, değilse `false`; `leaf` checkpoint'i taşıyan çocuk issue numarasıdır |
| `updated_at` | Epic issue'sunun `updatedAt` değeri; yalnız ISO-8601 biçimi kabul edilir, `gh` alanı vermezse ya da metin ISO-8601 değilse `null` |
| `url` | `tracker.repo` varsa GitHub issue bağlantısı, yoksa `null` |
| `leaves[]` | Epic `children` numaralarından issue listesinde bulunanlar: `{number, title, state}`; seal şartı yok, kapalı çocuklar da listelenir; `state` etiket önceliği `leaf-done` > `blocked` > `deferred` > `executing` > `agent-approved` > `intake` > `closed`/`open` |
| `counts` | `epics` = listelenen epic sayısı, `leaves` = bu epic'lerin `leaves[]` toplamı, `blocked` = `blocked` etiketli tüm issue'lar |
| `warnings` | Kısa Türkçe uyarı metinleri |

`stale: true` yalnızca durum eksikse: kit kökü yok, `gh` okunamadı ya da
çevrimdışı modda önbellek yok. Çevrimdışı önbellek isabeti `stale: false`.
`kit.dirty`: `true` kirli, `false` temiz, `null` git durumu okunamadı.
`gate`: `pass`, `fail` veya gate koşulmadıysa `null`; çevrimdışı okumada
`--with-gate` verilmezse `null` kalır (veri uydurulmaz).

Çıkış kodları: `0` başarı (uyarılar dahil), `1` proje bulunamadı ya da
`kit.config.yaml` geçersiz, `2` hatalı CLI argümanı.

## Eval özeti

`evaluations` bloğunun kaynağı proje kökündeki `.kit/evaluations.json`; dosya
salt-okur, `status.py` ona yazmaz. Dosya yoksa blok yine vardır ve tüm alanlar
`null` olur.

```json
{
  "demir_kit_version": "2",
  "epics": {
    "286": {
      "batch": "batch-7",
      "cases_pass": 12,
      "cases_total": 14,
      "discovery_rate": 0.8,
      "findings": {"friction": 3, "objection": 0, "opportunity": 0},
      "updated_at": "2026-11-09T10:00:00Z"
    }
  }
}
```

- Epic anahtarı issue numarasının string hali; yalnız `^[1-9][0-9]*$` kabul
  edilir (`012`, `+12`, `-5`, boşluklu anahtar uyarı verip atlanır).
- `batch` boş olamayan string, `cases_pass`/`cases_total` negatif olmayan ve
  `2**53` sınırını aşmayan tam sayı, `cases_pass <= cases_total` olmalı.
- `discovery_rate` 0..1 arası sonlu sayı; çıktıda her zaman `float` olur.
- `findings` üç alanı (`friction`, `objection`, `opportunity`) negatif olmayan
  tam sayı ya da `null`.
- `updated_at` ISO-8601 ve gerçek takvim günü olmalı (`2026-02-31` geçersiz).

Geçersiz dosya, geçersiz anahtar ya da geçersiz alan komutu düşürmez; ilgili
alan `null` olur, `warnings[]` kısa bir uyarı taşır ve çıkış kodu `0` kalır.
Eski sürümün `evaluations` taşımayan önbelleği `--offline`da all-null blokla
kabul edilir.

`gh issue list` `--state all` ile çağrılır (en çok 500 issue): kapalı epic ve
leaf'ler de gelir. Varsayılan çıktı kapalı epic'leri (`epic-done` ya da kapalı
issue) atlar; bu yüzden günlük panelde yalnız açık iş görünür. Bir epic'in
`leaves[]` listesi tüm çocuklarını taşır (kapalılar dahil), `counts.leaves` de bu
listelerin toplamıdır. Epic'in `leaves[]` listesi `children` içinde adı geçen ve
issue listesinde bulunan çocukları taşır; seal'i olmayan çocuk da başlığı ve
durumuyla listelenir, seal yalnız `checkpoints[]` listesini besler. `--all-epics`
kapanmış epic'leri de aynı biçimde listeler.

## Önbellek

`.orchestration/status-cache.json`; zarf `{saved_at, args, data}`.
`args` parmak izi `with_gate`, `with_cost`, `full`. TTL aşılırsa, argüman
parmak izi değişirse ya da içerik sözleşmeye uymuyorsa önbellek yok sayılır ve
canlı hesaplanır. Çevrimdışı modda TTL ve argüman parmak izi yok sayılır.

## Salt-okunur garanti

Tek yazma önbellektir ve yalnız `--cache-ttl > 0` iken yapılır; başka dosya
oluşturulmaz. `gh` yoksa ya da oturum yoksa komut düşmez: `epics: []`,
`stale: true` ve uyarı döner, çıkış kodu `0` kalır.

## Örnek

```json
{
  "contract_version": 1,
  "generated_at": "2026-11-04T09:24:34Z",
  "stale": false,
  "source": "live",
  "kit": {"version": "2.56.0", "pin": "cf84b2c", "dirty": false},
  "project": {"name": "demir-kit", "profile": "kit-internal",
              "repo_root": "/Users/owner/repo",
              "tracker": {"provider": "github", "repo": "owner/repo"}},
  "epics": [{
    "number": 12, "title": "Epic", "state": "executing", "risk": null,
    "checkpoints": [
      {"id": "CP-1", "title": "status", "done": true, "leaf": 13},
      {"id": "CP-2", "title": "panel", "done": false, "leaf": 13}
    ],
    "updated_at": "2026-11-04T09:00:00Z",
    "url": "https://github.com/owner/repo/issues/12",
    "leaves": [{"number": 13, "title": "Leaf", "state": "agent-approved"}],
    "gate": "pass",
    "open_findings": 0, "approvals": {"agent_approved": false, "human_qa": false},
    "next_action": null, "cycle_minutes": null, "cost_delta": null,
    "evaluations": {
      "batch": "batch-7", "cases_pass": 12, "cases_total": 14,
      "discovery_rate": 0.8,
      "findings": {"friction": 3, "objection": 0, "opportunity": 0},
      "updated_at": "2026-11-09T10:00:00Z"
    }
  }],
  "counts": {"epics": 1, "leaves": 1, "blocked": 0},
  "warnings": []
}
```
