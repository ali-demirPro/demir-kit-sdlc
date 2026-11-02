# Epic closure (ponytail önleme)

Tüm leaf'ler bitince **zorunlu**. Bu rapor `status: pass` olmadan epic
**`epic-done` olmaz**. Şema: [closure.schema.json](../schemas/closure.schema.json).

## Kim

| Adım | Roller |
|------|--------|
| Kapsam mutabakatı | analist + orchestrator |
| Teknik gap | architect + tester |
| Yanlış / gereksiz iş | adversarial mantığı (tester veya review CP) |
| Rapor + metrik | documenter |
| İnsan | epic kabulü → `epic-done` |

## 1 — Kapsam mutabakatı (analist)

- [ ] Epic KEEP listesi ↔ tüm child issue'lar
- [ ] Her child: `leaf-done` **veya** `deferred` + defer issue linki
- [ ] Orphan: kapanmış iş scope'ta yok mu?
- [ ] Zombie: `intake` / açık leaf unutulmuş mu?

Fail → `epic-reconcile` issue aç veya eksik child'ları listele.

## 2 — Borç check-in (architect)

Refactor tetikleri ([refactor-triggers.md](../policies/refactor-triggers.md))
taranır; bu adım epic kapanışında yapılır ve sonucu closure raporunda görünür.

- [ ] Hotspot: en çok değişen dosyalar ve en büyük dosyalar listelendi.
- [ ] Aynı modülde üç fix kaydı var mı? (`learnings.py --digest`)
- [ ] `Strong` bulgu varsa yeni leaf/epic önerisi açıldı.
- [ ] Kapsam dışı bırakılan her bulgu closure raporunda gerekçesiyle görünür.

Sessiz erteleme yoktur: borç ya leaf açar ya da gerekçesiyle kayda geçer.

## 3 — Gap analizi (architect + tester)

- [ ] Her leaf: `doctor.sh --issue N` 0 hata + evidence `pass`
- [ ] `depends_on` ihlali yok
- [ ] Epic amacı dışı dosya/PR kapsamı

## 4 — Gereksiz iş

- [ ] Duplicate iş
- [ ] Path routing dışı agent çalışmış mı?
- [ ] Revert / temizlik önerisi

## 5 — Rapor

Epic comment'ine `demir-kit-closure` bloğu post et:

````markdown
```yaml
demir-kit-closure
demir_kit_version: "2"
epic: 1
status: pass
gaps: []
unnecessary: []
deferred: []
metrics:
  leaf_count: 5
  cp_count: 5
  gate_retries: 0
  reconcile_issues: 0
  human_interventions: 0
  lead_time_hours: 2.5
  worker_count: 6
  tokens_in: 920000
  tokens_out: 41000
  cache_read: 18400000
  context_peak: 121000
  cost_usd: 0.82
ready_for_human_qa: true
```
````

- Worker sayıları: `python3 delivery/scripts/usage.py --run <run_id> --json`.
- Biten terminaller: `python3 delivery/scripts/worker_cleanup.py --run <run_id> --apply`.
- `status: fail` → `epic-reconcile` + yeni issue; **epic-done yasak**.
- Metrik tanımları ve retro: [metrics/README.md](../metrics/README.md).
- Doğrulama: `doctor.sh --issue <epic>` closure bloğunu (issue body veya comment)
  şemaya göre denetler. `epic-done` öncesi çalıştır.

## 6 — İnsan raporu ve kabul

Closure `pass` sonrası iki şey yapılır:

1. **Kısa onay notu** — epic issue'suna:

```bash
python3 delivery/scripts/update.py --issue <epic> --kind summary \
  --who orchestrator --what "Ne bitti" --decision "Ana karar" \
  --problem "Sorun / yok" --next "Kalan iş" \
  --approval yes --ask "Epic'i kapatıyor muyuz?"
```

- Onay satırı zorunlu; `--approval yes` `human-qa` etiketini ekler.

2. **Detaylı iş raporu** — aynı issue'ya, kısa özetten **sonra**:

```bash
python3 delivery/scripts/report.py --issue <epic> --post
```

- Kim (ana agent, reviewer, worker, insan), süreç, süre, maliyet/token,
  kararlar, sorunlar, kanıt.
- Teknik ID'ler `<details>` içinde; ana metin insan dili.
- Maliyet ölçülemediyse “ölçülemedi” yazar; tahmin edilmez.
- Claim snapshot'ı varsa **ana oturum (epic)** delta'sı; yoksa ana oturum
  toplamı ayrı satırda gösterilir.

- Aynı kısa özet sohbet sonunda da verilir.
- **Tek epic PR'ı**: `epic-<E>` → `main`. `delivery-doctor` yeşil olmadan merge
  edilmez; merge insan kabulüdür. Squash değil merge commit kullanılır.
- İnsan onayı: [human-qa-done](../policies/human-qa-done.md) epic bölümü →
  İnsan, issue'ya `demir-kit-accept` bloğunu **kendi GitHub hesabıyla** yazar;
  ardından `transition.sh --issue N --to epic-done` çalışır. Transition bloğu
  yazmaz; yalnız insan-authored bloğu doğrular. `--accept "<login>"` yalnız
  ek doğrulama içindir. Şablon:

```yaml
demir-kit-accept
demir_kit_version: "2"
epic: <epic-no>
by: <github-login>
decision: accepted
```

  `by` GitHub login'iyle eşleşmezse veya son insan kararı `rejected` ise epic
  kapanmaz.

- `transition.sh --to epic-done` merge edilmiş PR'ı ve temiz worktree'yi doğrular;
  ana checkout'tan çalıştırıldıysa `epic-<E>` worktree'sini siler
  (`--keep-worktree` ile korunur). Kapanmış epic worktree'leri:
  `epic_worktree.py prune`.

## Kurallar

- Agent "epic bitti" demez; yalnızca closure `pass`/`fail`.
- Closure atlanamaz; insan sorma yalnız kabul adımında.
