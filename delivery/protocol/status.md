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
| `--full` | Rezerve; şimdilik ek alan üretmez |

## Sözleşme

| Alan | Anlam |
|------|-------|
| `contract_version`, `generated_at` | Sözleşme sürümü (şu an `1`) ve UTC ISO-8601 üretim damgası |
| `stale`, `source` | Durum eksik mi; `live` taze, `cache` önbellek |
| `kit` | `version`, `pin` (kısa SHA), `dirty` |
| `project` | `name`, `profile`, `tracker.provider`, `tracker.repo` |
| `epics[]` | `number`, `title`, `state`, `risk`, `checkpoints.done/total` (`done` = `leaf-done` çocukların CP toplamı), `gate`, `open_findings`, `approvals`, `next_action`, `cycle_minutes`, `cost_delta` |
| `counts` | `epics`, `leaves`, `blocked` |
| `warnings` | Kısa Türkçe uyarı metinleri |

`stale: true` yalnızca durum eksikse: kit kökü yok, `gh` okunamadı ya da
çevrimdışı modda önbellek yok. Çevrimdışı önbellek isabeti `stale: false`.
`kit.dirty`: `true` kirli, `false` temiz, `null` git durumu okunamadı.
`gate`: `pass`, `fail` veya gate koşulmadıysa `null`; çevrimdışı okumada
`--with-gate` verilmezse `null` kalır (veri uydurulmaz).

Çıkış kodları: `0` başarı (uyarılar dahil), `1` proje bulunamadı ya da
`kit.config.yaml` geçersiz, `2` hatalı CLI argümanı.

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
              "tracker": {"provider": "github", "repo": "owner/repo"}},
  "epics": [{
    "number": 12, "title": "Epic", "state": "executing", "risk": null,
    "checkpoints": {"done": 0, "total": 2}, "gate": "pass",
    "open_findings": 0, "approvals": {"agent_approved": false, "human_qa": false},
    "next_action": null, "cycle_minutes": null, "cost_delta": null
  }],
  "counts": {"epics": 1, "leaves": 1, "blocked": 0},
  "warnings": []
}
```
