# DevOps — macOS

**Capability:** `platform.macos` · **Min level:** expert
**Gate:** `behavior`, `platform`

## Kapsam

macOS build hattı: komut satırından derleme, paketleme, imzalama, notarization
ve güncelleme. Xcode GUI'si varsayılmaz.

## Girdiler

- Build betiği, hedef mimari, minimum macOS sürümü.
- İmza kimliği ve notarization hesabı.
- Dağıtım kanalı kararı.

## Yöntem

1. **Build:** `swift build`/`xcodebuild`, çıktı `.app` bundle'ına paketlenir.
2. **İmza:** içten dışa, hardened runtime + timestamp.
3. **Notarization:** `notarytool submit --wait` + `stapler` (DMG'ye veya
   arşivden önce `.app`'e).
4. **Doğrulama:** temiz makinede `spctl -a -vv`.
5. **Kanal:** imzalı appcast; geri dönüş adımı.
6. **Kayıt:** sürüm, imza kimliği, notarization id.

## Kanıt

- Build logu, `codesign -dv`, `spctl` çıktısı.
- Notarization submission id.
- Appcast ve geri dönüş planı.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Build | CLI'dan tekrarlanabilir |
| İmza | İçten dışa, timestamp |
| Bilet | Staple'lı, `spctl` kabul |
| Kanal | Tek kanal veya ADR |

## Anti-pattern'ler

- Ad-hoc imza ile dağıtım.
- Zip'i staple etmeye çalışmak.
- Geri dönüş planı olmadan yayın.

## Handoff

Tester'a: temiz makine doğrulama adımı.
Release'e: sürüm ve indirme bağlantısı.
