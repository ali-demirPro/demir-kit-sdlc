# How

1. Mevcut şemayı ve erişim desenini oku.
2. İleri/geri migration adımlarını yaz; her adım idempotent mi?
3. Backfill hacmi, süre, kilit ve hata durumu.
4. Rollback ve veri kaybı riski; yıkıcı adım var mı?
5. Analitik event şeması ve retention politikası.
6. Bulguları `DM-*`; verdict `approved` | `revise_required`.

## Contract
- **Input:** leaf seal, şema, migration diff, veri hacmi.
- **Output:** migration planı, `DM-*`, rollback/backfill kanıtı.
- **Done when:** migration + rollback test edildi, veri kaybı yok.
- **Forbidden:** yıkıcı migration'ı insan kapısı olmadan onaylamak.
- **Handoff:** developer, tester, devops.
