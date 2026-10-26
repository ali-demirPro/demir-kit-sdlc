# Path routing — iş tipine göre agent alt-grafı

Orchestrator her leaf/epic için `path_id` seçer. Tek kaynak
[registry.yaml](../registry.yaml); bu dosya yalnız karar sırasını açıklar.

## path_id listesi

| path_id | Ne zaman | Aktif roller | On-demand |
|---------|----------|--------------|-----------|
| `pure_technical` | refactor, bugfix, CI, chore; UI/store yok | analist, developer, tester, devops, documenter | architect |
| `ui_feature` | UI/UX değişikliği | analist, designer, developer, tester, devops, documenter | architect |
| `full_product` | Greenfield / çok yüzey; signals belirler | analist, designer, developer, tester, devops, marketing/stores, marketing/landing, documenter | architect, growth/run |
| `store_release` | ASC / Play odaklı sürüm | analist, designer, developer, tester, devops, marketing/stores, documenter | architect, growth/run |
| `landing_only` | Landing / SEO / GTM | analist, designer, developer, tester, devops, marketing/landing, documenter | architect, growth/run |
| `experiment` | A/B, rollout, feature flag | `ui_feature` + growth/run | architect |

`on_demand`: yalnız boundary riski, `depends_on` karmaşası veya risk seviyesi
gerektiriyorsa çalışır. Çalışmayan roller "inactive"tir; ayrıca skip listesi tutulmaz.

## Sınıflandırma sırası

1. Seal `surfaces` ↔ `registry.yaml` `signals` (`match.surfaces`).
2. Title/body anahtar kelimeleri (seal bloğu hariç).
3. `entry.kind` fallback: `chore`/`bugfix` → `pure_technical`, `feature` →
   `ui_feature`, baseline'lar → `full_product`.
4. Labels (`release` vb.) yalnız ek sinyal; tek başına path seçmez.
5. Çakışma: **dar path kazanır**:
   `store_release` > `landing_only` > `experiment` > `ui_feature` >
   `pure_technical` > `full_product`.
6. Hiçbiri eşleşmezse: `ui_feature`; gerekçe comment'e yazılır.

`stacks` serbest metinle eşleştirilmez; gerçek proje stack'i seal/factory'den gelir.

## Çıktı

```yaml
delivery_path:
  path_id: pure_technical
  active_agents: [analist, developer, tester, devops, documenter]
  on_demand: [architect]
  inactive:
    - id: marketing/stores
      reason: dağıtım kapsamda değil
```

Inactive gerekçesi zorunlu; gerekçesiz agent çalıştırmak contract ihlalidir
([CONTRACT.md](../CONTRACT.md) I10).
