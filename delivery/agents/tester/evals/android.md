# Tester Android — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TA-1 | Process death test edilmedi | Case + state kontrolü | Atlanır |
| TA-2 | Yalnız tek API | Min + güncel API | Tek cihaz |
| TA-3 | TalkBack sırası bozuk | A11y fail | Yalnız contentDescription |
| TA-4 | Font scale 2.0 taşması | Case + screenshot | Atlanır |
| TA-5 | Play pre-launch crash | Rapor + blocker | Okunmaz |
| TA-6 | İzin "bir daha sorma" çıkmazı | Case + recovery | Test yok |
| TA-7 | Foldable layout kırık | Cihaz matrisi | Yalnız phone |
| TA-8 | Staged rollout planı yok | %5→%100 + rollback | Doğrudan %100 |
| TA-9 | Offline'da ANR | Logcat + blocker | Yok sayılır |
| TA-10 | Flutter parity testi yok | iOS/Android smoke | Tek platform |
