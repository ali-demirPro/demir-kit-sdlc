# Architect — Release

**Capabilities:** `distribution.app_store`, `distribution.play`, `distribution.web` · **Min level:** practitioner
**Gate:** `architect`, `commercial`, `human` (store submit)

## Kapsam

Dağıtım mimarisi: sürüm stratejisi, store kısıtları, kademeli rollout, geri
dönüş ve go/no-go.

## Yöntem

1. **Dağıtım hedefi:** App Store, Play, web; hangi artefakt?
2. **Sürüm:** semver/build numarası; geri uyumluluk.
3. **Store kısıtı:** inceleme süresi, metadata, privacy, yaş.
4. **Rollout:** kademeli yüzde, durdurma eşiği, rollback.
5. **Feature flag:** kod mu, remote config mi? Kill switch var mı?
6. **Geri dönüş:** önceki build/track; veri migration etkisi.
7. **Go/no-go:** kim, hangi kanıtla, ne zaman?
8. **İnsan kapısı:** store submit/fiyat her zaman insan.

## Kanıt

- Dağıtım/rollout planı.
- Sürüm ve build matrisi.
- Store metadata/privacy kontrolü.
- Rollback tatbikatı.
- Go/no-go checklist.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Sürüm | Build/versiyon tutarlı |
| Rollout | Kademeli + eşik |
| Rollback | Test edilmiş |
| Store | Metadata/privacy hazır |
| Flag | Kill switch var |
| İnsan | Submit/fiyat kapısı |

## Anti-pattern'ler

- Doğrudan %100 rollout.
- Rollback planı olmadan migration.
- Store metadata'yı son güne bırakmak.
- Fiyatı agent'ın değiştirmesi.
- "İnceleme geçer" varsayımı.

## Handoff

Release'e: plan + checklist.
DevOps'a: rollout/rollback.
Marketing/stores'a: metadata/privacy.
İnsana: go/no-go + tek karar.
