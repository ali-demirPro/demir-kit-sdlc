# User intents (command palette)

Kullanıcı doğal dilinde söyler → coordinator / skill tetikler. Teknik komut adı kullanıcıya okutulmaz.

| User says (examples) | Skill / action |
|----------------------|----------------|
| Kit kur, repoyu hazırla, vendor demir-kit | `kit-setup` → `kit-envision` → `kit-init` |
| Repoyu analiz et, vizyon sor, platform tartış | `kit-envision` |
| Yönü onayladım, ecosystem yaz | `discovery-approved` → `kit-init` |
| Yeni proje, fikir var, başlayalım | `kit-envision` → `scope-triage` → … |
| Feasibility, yapılabilir mi, risk analizi | `scope-triage` + update `feasibility` |
| Scope sık, özellik kes, MVP netleştir | `scope-triage` (re-run) |
| Roadmap, neredeyiz, ne kaldı | GitHub Project / issue CP checklist; optional comment from `weekly-adaptive-loop` |
| Blocker, ne engelliyor | `coordinator-blockers.md` scan + issue labels |
| Haftalık check-in, hafta planı | `weekly-adaptive-loop` template comment |
| Mimari karar, stack, free tier | `solution-architect` (`decision` / `tier-review`) |
| Positioning, ICP, kime satıyoruz | `product-strategy` |
| Fiyat, abonelik, IAP modeli | `monetization-brief` (+ insan onayı) |
| Launch, ASO, kanal, marketing | `gtm-lite` |
| Landing / store metin uyumu | `commercial-review` |
| Planı mühürle, agent başlasın | `work-package` seal → Orca |
| Scope değişti | `work-package-amend` |
| Öğrenilenler, retro | `learnings` |

## Coordinator

Map intent from chat; do not require exact phrases. Prefer one clarifying `ask` if ambiguous (build vs discover).
