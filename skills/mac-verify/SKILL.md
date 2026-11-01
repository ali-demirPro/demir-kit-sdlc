---
name: mac-verify
description: >-
  macOS davranış ve görünüm kanıtı: self-test, snapshot, debug köprüsü ve
  light/dark karşılaştırması. Use when a macOS surface needs a behavior gate,
  when snapshots must prove a UI change, or when a gate has no runnable command.
---

# mac-verify

macOS projesinde "çalışıyor" iddiasını ölçülebilir kanıta çevirir. Simülatör
yoktur; gerçek pencere, gerçek store ve gerçek imza vardır.

## Sözleşme: her yüzey üç komut yayınlar

`ecosystem.yaml` altında tanımlanır:

```yaml
gates:
  behavior: "./build.sh && ./tools/selftest.sh"
  selftest: "./tools/selftest.sh"
  snapshot: "./tools/snap.sh"
```

- `behavior` gate komutu `{checkpoint}` alır ve **exit 0** döner.
- `selftest` aynı işi uygulama içinde koşar; PASS/FAIL satırı basar.
- `snapshot` sayfa başına PNG üretir.

Üçü de yoksa yüzey hazır değildir: `health-check` `ready: false` verir.

## Self-test

- `--selftest` bayrağıyla çalışır, store **`/tmp`** altında olur.
- Her adım `PASS`/`FAIL` satırı basar; süreç exit 0/1 ile biter.
- Kullanıcının gerçek verisine asla dokunmaz.
- Kapsam: saf mantık, ekleme/silme, geri alma, menü komutunun çağırdığı eylem.
- Arka plan işleri için kısa "smoke" adımı (zamanlayıcı, gözlemci) eklenir.

## Snapshot

- Light ve dark, her dokunulan sayfa için ayrı PNG.
- Seed verisi açık (`APP_SEED=1` benzeri); boş ekran kanıt sayılmaz.
- Pencere **aktif** olmalı; inaktif pencerenin soluk metni review edilmez,
  karşılaştırma `comparison_valid: false` sayılır.
- Tam ekran yakalama yapılmaz; yalnız uygulamanın kendi penceresi.

## Refactor modu

Refactor leaf'inde aynı viewport, aynı seed ve aynı appearance kullanılır;
beklenen sonuç **aynı** snapshot hash'idir (`ui_unchanged: true`).

## Debug köprüsü

Self-test'in ulaşamadığı şeyler için: global kısayol, panel, izin, zamanlama.

- `status`: izinler, açık paneller, son hata.
- Aksiyon başına komut (menü başlığıyla aynı ad).
- `snapshot:<window>`: tek pencereyi PNG'ye çizer.

## Kanıt

- Self-test çıktısı (satır satır) + exit kodu `verification.local_gate`'e.
- Snapshot yolları ve `*-layout.json` dosyaları.
- Hangi kontrolün manuel yapıldığı.

## Anti-pattern'ler

- Gerçek veritabanına karşı test koşmak.
- Yalnız light modda snapshot almak.
- "Elle denedim" ile davranışı kapatmak.
- İnaktif pencereyi düzelterek "bulgu" üretmek.

## Done when

Üç komut da tanımlı ve `selftest` exit 0 veriyor; dokunulan her sayfa için light
ve dark snapshot alındı ve kanıt issue'ya yazıldı.
