# Execution protocol

Bir leaf'in `agent-approved` → `leaf-done` yolculuğu. Sözleşme:
[CONTRACT.md](../CONTRACT.md).

## 1. Kuyruk

Seçim `scripts/next-leaf.sh` ile yapılır; elle "sıradaki ne?" sorulmaz.

Bir leaf adaydır ancak:

- açık ve `agent-approved` etiketli,
- `executing`, `blocked`, `deferred`, `leaf-done` değil,
- `dependencies[].kind == blocks` olan tüm issue'lar çözülmüş (closed, `leaf-done`,
  `epic-done` veya `deferred`),
- aynı epic'te başka bir `executing` leaf yok (disjoint `depends_on` istisnası).

Sıra: en eski `createdAt` önce. Seçim sonucu issue numarasıdır.

## 2. Claim ve heartbeat

```bash
./delivery/scripts/next-leaf.sh --claim
```

Claim şunları yapar: `+executing`, assignee, `run: <id>` comment. Kalp atışı her CP
sonunda evidence comment'idir.

- Son kalp atışı > 2 saat ise claim bayatlar: `-executing`, `blocked` **değil**,
  "stale claim released" comment. Sonraki tur devralır.
- İki worker aynı leaf'e claim atamaz; ikincisi `executing` görüp çıkar.

## 3. Run

```bash
orca status --json
orca orchestration run-create --objective "demir-kit #<N>" --json
orca worktree create --name "wp-<N>" --issue <N> --json
```

Orca yoksa **degrade mod**: tek panelli agent aynı protokolü uygular; gate
komutlarını çalıştırır ve evidence comment'ini yazar. Etiket değişimi yine
`doctor.sh --issue N` yeşil olmadan yapılmaz.

### Worker yaşam döngüsü

`task-create` → `worker-start` → gate çalışması → `worker_done`. Coordinator
`check --wait` ile bekler. Degrade modda `worker_done` = gate exit 0 + evidence
comment; ayrı bir olay yoktur.

```bash
orca orchestration send --type worker_done --outcome succeeded   # veya failed
```

| Amaç | Komut |
|------|-------|
| Run | `orca orchestration run-create --objective …` |
| Task | `orca orchestration task-create --spec …` |
| Worker | `orca orchestration worker-start …` |
| Bekleme | `orca orchestration check --wait …` |
| Terminal | `orca terminal create --command …` + `terminal wait` |
| Worktree | `orca worktree create --issue N` / `worktree set` |

Komut adları Orca sürümüne göre değişebilir; `orca --help` ve `orca status --json`
tek doğruluk kaynağıdır. UI yakalama: `skills/ui-gate` (`goto`, `set device`,
`screenshot`; mobilde `orca-emulator` / `orca-emulator-android`).

## 4. CP döngüsü

CP'ler `depends_on` topological sırasında yürür. Her CP:

1. **behavior** — `tests_plan` case'leri; `ecosystem.yaml` komutu, `{checkpoint}` yerine CP id.
2. **review** — risk seviyesine göre: [quality-gates.md](../policies/quality-gates.md).
3. **evidence** — [evidence.md](evidence.md) şablonuyla issue comment.
4. Sonraki CP.

Review bağımsızdır: uygulayan onaylayamaz; reviewer'lar birbirinin çıktısını görmez.

## 5. Bütçeler

| Kırılım | Limit | Aşılınca |
|---------|-------|----------|
| behavior turu | 3 | `blocked` + `ask` |
| architect turu | 3 | `blocked` + `ask` |
| commercial turu | 3 | `blocked` + `ask` |
| adversarial turu | 5 | `blocked` + `ask` |
| UI yeniden çekim | 2 | `ask` (karşılaştırma geçersiz) |
| fixer döngüsü | 2 | `blocked` |
| leaf duvar saati | 4 saat | `blocked` |

Bütçe aşımı bir başarısızlık değil, **karar noktasıdır**: `policies/escalation.md`.

## 6. Resume

Bir run herhangi bir noktada ölebilir. Yeniden başlatma:

1. `leaf-done` → no-op, çık.
2. `agent-approved` → [health-check.md](health-check.md), sonra CP-1.
3. `executing` → issue comment'lerinden `demir-kit-evidence` bloklarını topla.
4. CP sırasında ilk `status: pass` olmayan CP'den devam et.
5. `pass` CP'yi **asla** yeniden koşma.

Bu algoritma idempotenttir; aynı leaf iki kez yürütülse bile sonuç aynıdır.

## 7. Leaf kapanışı

Tüm CP'ler `pass` ve risk gate'leri tamam ise:

```bash
./delivery/scripts/doctor.sh --issue <N>
gh issue edit <N> --add-label leaf-done --remove-label executing
```

`high` / `critical` ise önce `human-qa` etiketi ve insan kararı gerekir.
`low` / `medium` otomatik kapanır; insan spot-check yapar.

Kapanışta kısa bir ilerleme yorumu yaz:

```bash
python3 delivery/scripts/update.py --issue N --who developer --what "Leaf kapandı" --next "Epic kapanışı"
```

Epic seviyesinde otomatik closure başlar: `runbooks/epic-closure.md`.

Orca komutları ve task spec kuralları: [orca.md](orca.md).

## 8. Yasaklar

- `leaf-done` olmadan closure başlatmak.
- Evidence'sız CP'yi geçmiş saymak.
- `pass` CP'yi yeniden çalıştırmak.
- Aynı epic'te paralel leaf (disjoint deps yoksa).
- `agent-approved` olmadan kaynak değiştirmek (`scripts/guard.sh`).
- İnsana teknik jargonla soru sormak (`policies/escalation.md`).
