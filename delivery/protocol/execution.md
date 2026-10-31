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

Claim şunları yapar: `run claim` lease comment'i (`lease_until`, 2 saat),
`+executing`, assignee. Kalp atışı her CP sonunda evidence comment'idir.

- Eşzamanlı iki claim varsa **en küçük comment ID** kazanır; kaybeden assignee'sini
  bırakır ve sayı basmaz. Aynı leaf'e iki worker başlamaz.
- Lease bayatlarsa `next-leaf --release --issue N` ile bırakılır; `executing` ve
  assignee temizlenir, `run release` comment'i yazılır. Sonraki tur devralır.
- `--force --reason "..."` yalnız lease'den sonra evidence varsa veya aktif iş
  bilinçli bırakılıyorsa kullanılır; gerekçe comment'e yazılır.

## 3. Run — epic worktree

Bir epic = **tek worktree + tek branch + tek PR**. Leaf'ler aynı checkout'u
yeniden kullanır; her leaf için yeni worktree açılmaz.

```bash
# İlk leaf claim'inde bir kez:
orca status --json
orca worktree create --name "epic-<E>" --issue <E> --json
orca orchestration run-create --objective "epic #<E>" --json

# Her leaf/CP:
orca orchestration task-create --spec "<CP spec>" --task-title "<CP>" \
  --deps '["task_<önceki>"]' --run <run_id> --json
orca orchestration worker-start --task <task_id> \
  --worktree <epic-E path> --agent opencode2 --run <run_id> --json

# Resume:
orca orchestration run-use --id <run_id> --json
```

`next-leaf.sh --claim` epic worktree'yi bulur veya açar; çıktı sıradaki üç komutu
yazar. `guard.sh --issue N` kaynak değişikliğinin **doğru epic worktree'sinde**
olduğunu doğrular; ana checkout'tan commit engellenir.

`orca_capabilities.py` komut/flag şemasını `orca agent-context`'ten okur. Ürün
projeleri Orca sürümü **karşılaştırmaz**; kullanılan özellik yoksa degrade kaydı
ister. Kit kendi geliştirmesinde yeni Orca sürümlerine uyarlanır.

Yeni leaf'e başlamadan önce `git merge origin/main` (rebase yasak; evidence
commit SHA'ları korunur). `epic_worktree.py sync --epic E` bunu uygular.

İnsan kapısı `orca orchestration gate-create --task <task_id>` ile açılır;
onayda `gate-resolve` çözülür. Worker sorusu `ask/reply`, coordinator mesajı
`inbox` üzerinden yürür; GitHub yorumu kalıcı kayıttır.

### İlerleme ve durum

`update.py` her yorumda Orca worktree checkpoint'ini de yazar:
`worktree set --comment "<kısa>" --workspace-status in-progress|in-review`
ve insan kapısında `--unread`. GitHub yorumu kalıcı geçmiş, Orca notu canlı
durumdur.

Orca yoksa **degrade mod**: `git worktree add` ile yine epic worktree açılır.
Gerekçe `guard.sh --degrade --reason "..."` ile issue'ya `run degrade:` yorumu
olarak yazılır; evidence'ta `degrade` bloğu bulunur. Sessiz degrade yoktur.

### Worker yaşam döngüsü

`task-create` → `worker-start` → gate çalışması → `worker_done`. Coordinator
`check --wait` ile bekler. Degrade modda `worker_done` = gate exit 0 + evidence
comment; ayrı bir olay yoktur.

```bash
orca orchestration send --type worker_done --outcome succeeded   # veya failed
```

| Amaç | Komut |
|------|-------|
| Worktree (epic) | `orca worktree create --name epic-<E> --issue <E>` |
| Worktree durumu | `orca worktree current --json` / `worktree list --json` |
| Run (epic) | `orca orchestration run-create --objective "epic #<E>"` / `run-use --id` |
| Task (leaf/CP) | `orca orchestration task-create --spec … --deps …` |
| Worker | `orca orchestration worker-start --task <task_id> --worktree <epic path> …` |
| İzleme | `orca orchestration worker-show/read/list --run <run_id>` |
| Mesaj | `orca orchestration ask/reply/inbox/send` |
| Karar kapısı | `orca orchestration gate-create/gate-resolve/gate-list` |
| Bekleme | `orca orchestration check --wait …` |
| Terminal | `orca terminal create --command …` + `terminal wait` |
| Worktree silme | `orca worktree rm --worktree name:epic-<E>` |

Komut adları Orca sürümüne göre değişebilir; `orca --help` ve `orca status --json`
tek doğruluk kaynağıdır. UI yakalama: `skills/ui-gate` (`goto`, `set device`,
`screenshot`; mobilde `orca-emulator` / `orca-emulator-android`).

### Epic kapanışı

Tüm leaf'ler `leaf-done` olduğunda tek PR açılır: `epic-<E>` → `main`.
Merge insan kabulüdür; ardından `transition.sh --issue E --to epic-done` merge'i
ve temiz worktree'yi doğrular, worktree'yi siler (`--keep-worktree` ile korunur).

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
./delivery/scripts/transition.sh --issue <N> --to leaf-done
```

`transition.sh` doctor preflight'ını hedef etiket varsayımıyla çalıştırır;
geçmezse etiket değiştirmez. Etiketleri elle `gh issue edit` ile değiştirmek
contract ihlalidir.

`high` / `critical` ise önce `human-qa` etiketi ve insan kararı gerekir.
`low` / `medium` otomatik kapanır; insan spot-check yapar.

Kapanışta kısa bir ilerleme yorumu yaz:

```bash
python3 delivery/scripts/update.py --issue N --who developer --what "Leaf kapandı" \
  --next "Epic PR'ı" --approval no
```

`leaf-done` main'e merge beklemez; commit epic branch'inde kalır. Main'e giriş
yalnız epic PR'ı ile olur.

Epic seviyesinde otomatik closure başlar: `runbooks/epic-closure.md`.

`high` / `critical` insan kapısı varsa ilerleme yorumu `--human-gate` (veya
`--approval yes --ask "..."`) ile yazılır; aksi halde `update.py` hata verir.

Orca task spec'leri capability-aware'dir: `orca_plan` aktif capability/variant
dokümanlarını, gerekli reviewer rolleri ve variant gap'lerini taşır; plan çıktısı
`capabilities`, `active_variants`, `reviewers` alanlarını içerir.

`role` ve `reviewers` koordinasyon metadata'sıdır: mevcut `orca_wave` tek agent
(`opencode2`) başlatır; reviewer'lar ayrı worker/human olarak çağrılmalı ve
evidence'a rol/oturum kimliğiyle yazılmalıdır. Plan, reviewer'ı otomatik
başlatmaz.

Orca komutları ve task spec kuralları: [orca.md](orca.md).

## 8. State geçişleri

Tüm geçişler tek yazıcıdan yapılır:

```bash
./delivery/scripts/transition.sh --issue N --to scope-confirmed
./delivery/scripts/transition.sh --issue N --to agent-approved
./delivery/scripts/transition.sh --issue N --to executing      # claim'e delege
./delivery/scripts/transition.sh --issue N --to blocked --reason "…"
./delivery/scripts/transition.sh --issue N --to deferred --reason "…" --issue-link "#…"
./delivery/scripts/transition.sh --issue N --to leaf-done
./delivery/scripts/transition.sh --issue N --to epic-reconcile
./delivery/scripts/transition.sh --issue N --to epic-done --accept "ad" --report
```

`--dry-run` yalnız planı gösterir; `--json` makine çıktısı verir.

## 9. Yasaklar

- `leaf-done` olmadan closure başlatmak.
- Evidence'sız CP'yi geçmiş saymak.
- `pass` CP'yi yeniden çalıştırmak.
- Aynı epic'te paralel leaf (disjoint deps yoksa).
- Her leaf için ayrı worktree açmak; epic worktree'si varken ana checkout'ta çalışmak.
- Epic branch'ini rebase etmek (evidence commit SHA'ları bozulur).
- `agent-approved` olmadan kaynak değiştirmek (`scripts/guard.sh`).
- İnsana teknik jargonla soru sormak (`policies/escalation.md`).
