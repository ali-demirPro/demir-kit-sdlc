# Proje öncelikleri

Hedef projenin kritik öncelikleri; agent'lar işe başlamadan önce okur ve buna
uyar. Sözleşme: [CONTRACT.md](../CONTRACT.md) · Beyan yeri:
`kit.config.yaml` → `product.priorities`. Kural: [quality-gates.md](quality-gates.md).

## Beyan

```yaml
# kit.config.yaml
product:
  priorities:
    design_system: docs/design/tokens.md   # varsa: tasarım sistemi kaynağı
    architecture:                          # korunacak mimari dokümanlar
      - docs/architecture/boundaries.md
      - docs/architecture/cost-and-tiers.md
    quality_floor: "test + lint yeşil; kapsam dışı refactor yok"
```

## Kurallar

| # | Kural |
|---|-------|
| P1 | **Design system varsa uyulur.** Token, bileşen ve desenler birebir kullanılır; yeni desen uydurulmaz. Tasarım sistemi sustuğunda soru sorulur, tahmin edilmez. |
| P2 | **Mimari korunur ve güçlendirilir.** Mevcut sınırlar (boundary) ihlal edilmez; genişletme mimari karar (ADR) veya `architect` gate'i ile olur. "Kolay olsun diye" sınır aşımı yoktur. |
| P3 | **Plana sadakat.** Yalnız mühürlü kapsam (`tests_plan`, `checkpoints`) uygulanır. "İyi olurdu" eklemeleri, sessiz refactor ve kapsam dışı iyileştirme yoktur; yeni iş ayrı leaf'tir. |
| P4 | **Kalite zemini düşmez.** Mevcut test/lint/gate'ler yeşil kalarak ilerlenir. Kalite düşüren "kısayol" çözüm değildir; kapılar gevşetilmez. |
| P5 | **Uydurma yok.** Var olmayan API, dosya, kural veya "projede şöyleydi" bilgisi üretilmez; emin olunmayan konu kaynak gösterilerek doğrulanır. |

## Yürütme bağları

- **Seal:** leaf `reference.paths`'a design system ve mimari dokümanlar eklenir
  ([seal.md](../protocol/seal.md)).
- **Brief:** `brief.py` proje önceliklerini agent brief'ine taşır — her işte
  görünür.
- **Denetim:** `doctor --product` beyan edilen yolların varlığını doğrular.
- **Sapma:** önceliklere aykırı bir keşif olursa iş durdurulur (`blocked`) veya
  kapsam değişikliği için yeni leaf açılır; sessizce yön değiştirilmez.