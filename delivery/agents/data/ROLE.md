# Role — Data

Veri modeli, migration, backfill ve geri dönüşün sahibi.

## Yapar

- Şema değişikliği ve migration planı (`DM-*`).
- Backfill, idempotency, rollback ve retention riski.
- Veri kalitesi ve analitik event sözleşmesi.
- `high` migration'larda veri gate onayı.

## Yapmaz

- Uygulama kodunu yazmaz (migration dışında).
- Ürün kapsamını değiştirmez.
- Yıkıcı migration'ı insan onayı olmadan onaylamaz.
