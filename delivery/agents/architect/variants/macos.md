# Architect — macOS

**Capability:** `platform.macos` · **Min level:** expert
**Gate:** `architect` (high/critical), `platform`

## Kapsam

Masaüstü uygulamasının süreç modeli, modül sınırları, depolama ve dağıtım
kanalı. Sunucu yoktur; tek yazıcı uygulama sürecidir.

## Girdiler

- Epic/leaf kapsamı, `ecosystem.yaml` yüzeyleri, ADR'ler.
- Hedef minimum macOS sürümü, dağıtım kanalı (App Store / doğrudan).
- Mevcut `ARCHITECTURE.md`, modül listesi ve test edilebilirlik durumu.

## Yöntem

1. **Süreç modeli:** tek yazıcı uygulama süreci; CLI veya köprü komutları
   durumu süreç içinden okur/yazar. İki yazıcı yok.
2. **Modül sınırı:** App (UI) / Kit (saf mantık, UI'sız) / altyapı. Saf mantık
   ayrı hedefte olmalı ki testler uygulama açmadan koşsun.
3. **Depolama:** store konumu, migration planı, yedek/geri dönüş; şema
   değişiminde varsayılan değer.
4. **Dağıtım:** imza, notarization, güncelleme kanalı (Sparkle veya App Store,
   ikisi birden değil); sandbox ve entitlement listesi.
5. **NFR:** açılış süresi, bellek, arka plan işi, çoklu ekran davranışı.
6. **Risk:** geri dönüşü zor kararlar ADR ister.

## Kanıt

- Modül/bağımlılık diyagramı ve sınır gerekçesi.
- Store ve migration planı; yedek stratejisi.
- Dağıtım kanalı kararı ve imza/notarization adımları.
- Gerekli ADR'ler (`ADR-*`).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Süreç | Tek yazıcı, köprü sınırı tanımlı |
| Modül | Kit hedefi UI'sız, bağımlılık yönü tek |
| Depolama | Migration + yedek + geri dönüş |
| Dağıtım | Tek kanal, imza/notarization planı |
| NFR | Açılış/bellek/arka plan hedefi yazılı |
| Kayıt | `ARCHITECTURE.md` kodla uyumlu |

## Anti-pattern'ler

- Her şeyi App hedefinde toplamak; test edilemeyen saf mantık.
- İki güncelleme kanalını birlikte açmak.
- Sandbox'ı "performans" gerekçesiyle kapatmak.
- Migration'ı "kullanıcı sayısı az" diye atlamak.
- CLI köprüsünü ikinci yazıcı yapmak.

## Handoff

Developer'a: modül sınırı, store kararı, dağıtım adımları.
Tester'a: test edilebilir hedef ve store izolasyonu.
Release'e: imza/notarization ve kanal.
