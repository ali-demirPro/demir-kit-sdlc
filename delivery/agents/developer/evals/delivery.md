# Developer delivery — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DPD-1 | Flagsiz büyük değişiklik | Flag + kademeli | Doğrudan |
| DPD-2 | Migration kodla aynı deploy | Ayrı/geri uyumlu adım | Aynı anda |
| DPD-3 | Smoke yok | Deploy sonrası smoke | Kör deploy |
| DPD-4 | Rollback denenmemiş | Flag/artefakt geri dönüş | Plan var |
| DPD-5 | Build commit'siz | İzlenebilir artefakt | Belirsiz build |
| DPD-6 | Prod'da debug log | Seviye ayarı | PII/ses |
| DPD-7 | Cache purge yok | Invalidation | Stale |
| DPD-8 | Health check yok | Readiness/liveness | Trafik erken |
| DPD-9 | Deploy marker yok | Marker + SLO | Korelasyon yok |
| DPD-10 | Geri dönüş süresi bilinmiyor | Hedef süre + tatbikat | Tahmin |
