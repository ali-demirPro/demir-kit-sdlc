# Tester iOS — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TI-1 | Yalnız simülatör | Fiziksel cihaz/TestFlight | Simülatör yeter |
| TI-2 | Dynamic Type XXL test edilmedi | Case + screenshot | Atlanır |
| TI-3 | VoiceOver sırası bozuk | A11y fail | Yalnız label |
| TI-4 | İzin reddi çöküyor | Case + blocker | Test yok |
| TI-5 | Arka plan sonrası state kaybı | Lifecycle case | Atlanır |
| TI-6 | TestFlight build eski | Güncel build iste | "Aynı kod" |
| TI-7 | Offline'da spinner sonsuz | Timeout case | Yok sayılır |
| TI-8 | iPad layout kırık | Cihaz matrisi | Yalnız iPhone |
| TI-9 | Flaky XCUITest | Karantina + trace | Silinir |
| TI-10 | Ekran kaydı yok | Trace/recording | Sözlü kanıt |
