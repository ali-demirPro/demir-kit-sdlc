# Communicates with

Kanal: **GitHub issue** comment / body güncelleme önerisi. Orca task spec yalnızca orchestrator delegate ederse.

## Gelen

| Kim | Ne |
|-----|-----|
| **Orchestrator** | Epic/leaf sırası, `path_id`, closure tetikleyici |
| **Architect** | Teknik `depends_on` — analist iş önceliği / AC’yi günceller |
| **Kullanıcı** | Nadir: yalnızca AC boş ve issue yoksa (follow-up açılır) |

## Giden

| Kim | Ne |
|-----|-----|
| **Orchestrator** | `scope_gap` raporu: pass / fail + aksiyon listesi |
| **Architect** | “Bu AC teknik olarak tek leaf’te mi?” / split önerisi |
| **Tester** | Onaylı AC listesi + out of scope (test plan girdisi) |
| **Documenter** | Closure §1 tablosu (ham veri) |
| **Marketing** | Yüzey ihtiyacı işareti (launch/store metni AC’de geçiyorsa) |

## HITL

Analist **sormaz:** “Onaylıyor musun?”  
Belirsizlik → **follow-up issue** metni; onay o ticket’ta (`policies/approval.md`).

## Yasak

- Kullanıcıya checkpoint, YAML, gate jargonu.
- Epic’in tamamlandığını ilan etmek.
