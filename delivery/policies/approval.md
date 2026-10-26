# Onay politikası

Onay = GitHub issue + label. Sohbet onayı yalnız bilgi eksikse.

## Otonom devam (soru yok)

| Koşul | Sonraki adım |
|--------|--------------|
| Epic `scope-confirmed` + child listesi net | Plan + path routing |
| Leaf `agent-approved` + health-check `ready` | `executing` + CP döngüsü |
| CP gate'leri + evidence `pass` | Sonraki CP |
| Tüm CP'ler + risk `low`/`medium` | `leaf-done` |
| Tüm leaf'ler `leaf-done`/`deferred` | Epic closure (otomatik) |
| Follow-up issue açıldı ve label'ları var | Kendi akışında |

Orchestrator **sormaz:** "Onaylıyor musun?" — issue truth yeterli.

## İnsan kapısı (risk C)

| Durum | Kim |
|-------|-----|
| Risk `high` leaf kapanışı | ürün sahibi (kısa QA) |
| Risk `critical` | iki insan |
| Epic closure `pass` sonrası kabul | ürün sahibi |
| Store submit, prod deploy, fiyat, yıkıcı migration | her zaman insan |
| Bütçe aşımı, belirsiz AC, güvenlik bulgusu | ürün sahibi (tek soru) |
| Eksik issue / zorunlu label | ürün sahibi |

`low` / `medium` leaf'ler otomatik kapanır; insan **spot-check** yapar. Epic kabulü
her zaman insandır; bu, otonomi sınırıdır (I10).

## Follow-up ticket

Implement sırasında eksik iş → **yeni issue** aç.

- Onay **o ticket'ta** (scope/mühür/human-qa).
- Parent epic, reconcile tamamlanmadan `epic-done` olmaz.
- Sessiz kapsam büyütme yasak ([escalation.md](escalation.md) `SCOPE`).

## Yasak ifadeler

Closure raporu yokken:

- "Epic tamamlandı"
- "Her şey bitti"

İzinli: "Leaf #N kapandı (`leaf-done`)", "Epic closure bekliyor".
