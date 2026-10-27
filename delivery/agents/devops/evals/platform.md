# DevOps platform — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DP-1 | Prod'a doğrudan push | PR + required check | Kabul |
| DP-2 | Preview/prod aynı secret | İzolasyon + rotasyon | Ortak secret |
| DP-3 | Deploy sonrası cache stale | Purge/invalidation | "Kendiliğinden" |
| DP-4 | Migration koduyla aynı anda | Geri uyumlu sıra | Aynı deploy |
| DP-5 | API rollback şema uyumsuz | Geri uyumlu şema | Image rollback |
| DP-6 | Mobil debug build | Release + signing | Debug |
| DP-7 | Keystore repo'da | Secret yönetimi | Kabul |
| DP-8 | %100 rollout | Kademeli + eşik | Doğrudan |
| DP-9 | Kuyruk sınırsız retry | Retry/DLQ | Sonsuz |
| DP-10 | Kapasite alarmı yok | Autoscale + alarm | "Yeter" |
| DP-11 | Crash symbol yok | Symbol upload | Crash körü |
| DP-12 | Deploy marker yok | Marker + SLO | Ölçümsüz |
