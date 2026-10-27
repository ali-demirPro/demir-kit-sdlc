# Designer — Privacy

**Capability:** `quality.privacy` · **Min level:** practitioner
**Packs:** `apple-privacy`
**Gate:** `ui_visual`, `ui_interaction`, `comparison_valid`

## Kapsam

Arayüzde veri minimizasyonu, izin gerekçesi, consent ve privacy label tutarlılığı.

## Yöntem

1. **Minimizasyon:** formda yalnız gerekli alan; türetilebilir veri isteme.
2. **Amaç:** her alanın ne için istendiği kullanıcıya açık.
3. **İzin:** ATT/bildirim/konum; gerekçe + red senaryosu.
4. **Consent:** opt-in, geri çekme, karanlık desen yok.
5. **Label:** App Privacy/Data safety ile UI akışı aynı.
6. **Saklama:** kullanıcıya silme/çıkış yolu.
7. **Log/analytics:** PII yok; event adı minimal.
8. **Çocuk/yaş:** yaş kapısı ve veri hassasiyeti.

## Kanıt

- Alan/amaç tablosu.
- İzin akışı + red screenshot'ı.
- Consent metni.
- Privacy label eşlemesi.

## Gate rubriği

| Kriter | Pass |
|--------|------|
| Minimize | Gereksiz alan yok |
| Amaç | Açık |
| İzin | Gerekçe + red |
| Consent | Opt-in/geri çekme |
| Label | UI ile tutarlı |
| Silme | Yol var |

## Anti-pattern'ler

- Zorunlu gereksiz alan.
- "Kabul et" dışında seçenek yok.
- İzin öncesi veri toplamak.
- Label'ı sonra doldurmak.
- PII'yi event'e koymak.

## Handoff

Developer'a: alan/consent/izin.
Security/Privacy'ye: data map.
Stores'a: label metni.
