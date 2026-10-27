# Developer — Android

**Capability:** `platform.android` · **Min level:** expert
**Gate:** `behavior`, UI retest, platform

## Kapsam

Compose/View içinde lifecycle'a dayanıklı, test edilebilir değişiklik.

## Yöntem

1. **Kırmızı test:** unit/Compose test; önce fail.
2. **UI seçimi:** Compose mu View mı? Mevcut desene uy.
3. **Lifecycle:** process death, configuration change, restore.
4. **State:** `StateFlow`/`ViewModel`; UI tek yönlü akış.
5. **Depolama:** Keystore (secret), DataStore/DB; migration.
6. **İzinler:** red, "bir daha sorma", ayarlara yönlendirme.
7. **A11y:** semantics, TalkBack, font scale.
8. **Kanıt:** test + API/cihaz + logcat (fail).

## Kanıt

- Test sonucu + API/cihaz.
- Process death testi.
- TalkBack/font scale notu.
- Logcat/trace (fail için).

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Test | Kırmızı→yeşil |
| Lifecycle | Process death restore |
| State | Tek yönlü akış |
| Storage | Keystore/şifreli |
| İzin | Red + kalıcı red |
| A11y | TalkBack/font scale |

## Anti-pattern'ler

- Activity/Fragment'ta iş mantığı.
- Process death'i yok saymak.
- Secret'ı SharedPreferences'a yazmak.
- İzin reddinde çıkmaz.
- Main thread'de ağ/DB.

## Handoff

Tester'a: API/cihaz matrisi + logcat.
Release'e: build/track etkisi.
