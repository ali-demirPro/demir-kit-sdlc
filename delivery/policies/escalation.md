# Escalation policy

Blocker taksonomisi ve insan sorusu kuralları. Otonomi, **tanımlı** durumlarda durur;
rastgele yerlerde değil.

## Taksonomi

| Kod | Durum | Etiket | Aksiyon | İnsan |
|-----|-------|--------|---------|-------|
| `DEP` | `blocks` bağımlılığı açık | `blocked` | bağımsız CP/leaf öner | gerekmez |
| `BUDGET` | gate turu / süre aşıldı | `blocked` | seçenekli `ask` | evet |
| `ENV` | araç, auth, emulator, CI kırık | `blocked` | düzelt veya degrade | gerekirse |
| `AC` | AC belirsiz/çelişkili | `blocked` | iki net seçenek | evet |
| `EXT` | dış servis/API bekliyor | `blocked` | mock veya ertele | gerekirse |
| `SCOPE` | kapsam kayması | `epic-reconcile` | follow-up issue | hayır |
| `SEC` | güvenlik/auth/veri bulgusu | `blocked` + `human-qa` | düzeltme planı | **her zaman** |
| `STALE` | claim > 2 saat | — | `-executing` + comment | hayır |

## İnsan sorusu formatı

- **Türkçe**, en fazla 2 cümle, 2–4 seçenek.
- Teknik jargon yok: checkpoint, gate, YAML, worktree, orchestration yasak.
- Ayrıntı: [human-communication.md](human-communication.md).
- Her soru tek bir karar ister; "ne yapalım?" açık uçlu soru değildir.
- Cevap issue comment veya `human-qa` kararı olarak kaydedilir.

| Kötü | İyi |
|------|-----|
| Gate 3'te kaldık, ne yapalım? | Ödeme akışı iki turda geçmedi. Küçük parçaya bölelim mi, yoksa bu özelliği sonraki sürüme mi bırakalım? |
| Evidence eksik | Bu adımın kanıtı eksik. Testi yeniden mi çalıştıralım, yoksa kapsamı mı daraltalım? |

## Bütçe aşımı

1. `blocked` + comment: hangi gate, kaç tur, son bulgular.
2. Tek soru: **böl** / **ertele** / **kabul et (waive)**.
3. `waive` yalnız `decisions` kaydı + risk sahibi onayı ile.
4. Cevap yoksa leaf açık kalır; başka leaf'e geçilebilir (bağımsızsa).

## Unblock

- Bağımlılık kapandı → `-blocked`, health-check tekrar.
- Bütçe kararı verildi → `decisions` + `-blocked`.
- `SEC` → insan onayı olmadan `-blocked` yok.

## Yasaklar

- Sessizce kapsam büyütmek (`SCOPE` yerine yeni leaf).
- Aynı soruyu tekrar sormak; cevap issue'da yoksa önce oraya yaz.
- `blocked` leaf'i `leaf-done` saymak.
- İnsan kapısını "otonomi" gerekçesiyle atlamak (I10).
