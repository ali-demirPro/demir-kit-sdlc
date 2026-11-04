# MCP (salt-okunur)

Kit komutlarını MCP üzerinden ajana açar: stdio, JSON-RPC 2.0, tek satır
istek/yanıt. Sunucu `delivery/scripts/mcp_server.py`; protokol çekirdeği
`initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`.

## Amaç ve sınır

Ajanın sözleşmeyi okuması ve kapıları denetlemesi için beş araç sunulur.
Hepsi salt-okunur: proje dosyası, issue, etiket veya worktree yazmaz.

| Var | Yok |
|-----|-----|
| `status`, `brief`, `doctor`, `next_leaf_list`, `guard` | `seal`, `transition`, `claim`, `update`, `review`, `report` |
| Okuma ve denetim | Mutasyon, onay, etiket değişimi, commit, merge |

Yazma yetkisi ajanın kendi oturumunda kalır; MCP yalnız kanıt toplar.

## Araçlar

| Araç | Argüman | Döner |
|------|---------|-------|
| `status` | `project?`, `offline?`, `with_gate?`, `with_cost?` | Proje + epic özeti (`status.py --json`) |
| `brief` | `issue` (zorunlu), `cp?` | Leaf brief; `cp` verilince kompakt CP brief'i |
| `doctor` | `issue?`, `checkpoint?`, `strict?` | Statik denetim + kapı sonucu |
| `next_leaf_list` | — | Bağımlılık sırasına göre hazır leaf kuyruğu; claim yapmaz |
| `guard` | `issue` (zorunlu) | Worktree + risk kaynak kapısı |

Her araç tanımı `annotations.readOnlyHint: true` taşır; `doctor` bunu
`check_mcp_self` ile kendisi doğrular.

## Kayıt

### Orca

Yeni Orca sürümlerinde Settings → Integrations → MCP; kayıt repo kapsamlıdır
(yalnız bu proje). Bu yüzey yoksa (ör. 1.4.242) sunucuyu ajanın kendi
yapılandırmasına ekle; Orca MCP'yi ajan CLI'sına devreder.

Komut:

```bash
python3 <kit>/delivery/scripts/mcp_server.py --project <proje>
```

`<kit>` kit kökü (vendored ise proje içindeki `demir-kit/`), `<proje>`
`kit.config.yaml` bulunan dizin.

### OpenCode

`opencode.json` içine `mcp.demir-kit` eklenir; `command` bir dizidir.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "demir-kit": {
      "type": "local",
      "command": [
        "python3",
        "demir-kit/delivery/scripts/mcp_server.py",
        "--project", "."
      ],
      "enabled": true
    }
  }
}
```

Proje kökünden çalıştırıldığı için `--project .` yeterlidir.

## Güvenlik

Sunucu hiçbir şey yazmaz: dosya, issue, etiket, worktree ve git durumu
değişmez. Mutasyon araçları bilinçli olarak yoktur; `tools/list` yalnız beş
salt-okunur aracı döner. Bununla birlikte `status`, `brief`, `doctor`,
`next_leaf_list` ve `guard` alt süreç olarak `gh` çağırabilir; yani ağa
çıkabilir ve GitHub token'ını kullanabilir. `status --offline` ağa çıkmaz.
Alt süreç zaman aşımı 120 sn, çıktı 20.000 karakterde kırpılır.

## Kayıt doğrulama

`./delivery/scripts/doctor.sh --strict` içindeki `mcp` kontrolü sunucuyu
başlatır, `initialize` + `tools/list` yazar ve yanıtı doğrular: beş aracın
tam olarak bulunması ve her birinde `readOnlyHint: true` olması gerekir.
Sunucu 10 sn içinde yanıt vermezse ya da araç listesi saparsa doctor hata verir.

## Hata kodları

| Kod | Ad | Anlam |
|-----|-----|-------|
| `-32700` | Parse error | Satır geçerli JSON değil; süreç düşmez |
| `-32600` | Invalid request | İstek JSON nesnesi değil, `method` yok veya satır 1 MiB üstü |
| `-32601` | Method not found | Bilinmeyen metot |
| `-32602` | Invalid params | Bozuk `params`, eksik argüman, bilinmeyen araç |

Hata yanıtı `{"jsonrpc":"2.0","id":…,"error":{"code":…,"message":…}}`
biçimindedir; sunucu tek bir hatalı satır yüzünden kapanmaz.
