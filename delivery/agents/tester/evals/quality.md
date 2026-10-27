# Tester quality — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TQ-1 | Klavye focus tuzağı | Fail + trace | Atlanır |
| TQ-2 | VoiceOver sırası bozuk | A11y fail | Yalnız label |
| TQ-3 | Kontrast 3.1 | Fail | "Marka" |
| TQ-4 | Font scale 2.0 taşma | Fail | Atlanır |
| TQ-5 | Reduced motion | Animasyon kapanır | Zorunlu |
| TQ-6 | CWV bütçe aşımı | Fail + ölçüm | "Yavaş" |
| TQ-7 | p95 2s | Fail | Tek örnek |
| TQ-8 | Log'da email | PII fail | Sızıntı |
| TQ-9 | Alert sahipsiz | Fail | Gürültü |
| TQ-10 | Event duplicate | Fail | Şişme |
| TQ-11 | RTL bozuk | Fail | Ayna yok |
| TQ-12 | Uzun çeviri taşması | Fail | Kırpılma |
