# Bağlam bütçesi

Token maliyeti, modelin her adımda yeniden okuduğu **bağlam** ile büyür.
Ölçüm (dogfood, 2026-11): tek çalışma 8 epic'i aynı bağlamda yürüttü; bağlam
19k → 823k token'a çıktı, adım başına maliyet 8,5x arttı ve toplam maliyetin
%88'i bağlam 400k'yı geçtikten sonra ödendi. Kural: bağlamı iş sınırında
sıfırla, bir dosyayı bir kez ve yalnız gereken dilimde oku.

## Eşikler

| Ölçü | Uyarı | Sert sınır |
|------|-------|------------|
| Oturum bağlamı | 120k token | 200k token |
| Tek araç çıktısı | 2k token | 8k token |
| Worker başına okunan doküman | 3 dosya | 5 dosya |

Sert sınırda dur: kısa özet yaz (karar + dosya yolları + açık iş), yeni oturum
aç ve özetle devam et. Sessizce devam etmek yasak.

## Kurallar

1. **Epic başına yeni bağlam.** Bir epic bitince sonraki epic yeni oturumda
   başlar; `session move` ile bağlam epic'ler arasında taşınmaz. Aynı epic
   içinde CP sınırında özet + yeni oturum serbesttir.
2. **Koordinatör salt-okur.** Orchestrator diff, log veya dosya içeriği okumaz;
   keşfi subagent'a yaptırır ve en fazla 30 satır özet alır. Uygulama işi
   worker'ın oturumunda kalır.
3. **Bir kez oku.** Aynı dosya ikinci kez okunmaz; önceki okumanın özeti
   kullanılır. Tam dosya yerine `rg -n`, `sed -n '40,90p'`, `git diff --stat`.
4. **Çıktıyı sınırla.** Gate/test logu dosyaya yazılır (`> /tmp/gate.log`),
   bağlama yalnız son 40 satır girer. `git diff` tam dökümü yerine dosya başına
   hunk alınır; `gh api` çıktısı `--jq` ile daraltılır.
5. **CP brief ile başla.** Worker, seal'i ve dokümanları kendiliğinden okumaz;
   `brief.py --cp CP-x` çıktısıyla başlar. Doküman yalnız brief'teki satırı
   doğrulamak için açılır (`CONTRACT.md` ve `quality-gates.md` tam okunmaz).
6. **Yazma biçimi.** Var olan dosya `edit`/patch ile değişir; tam dosya yazma
   yalnız yeni dosyada kullanılır. Yazılan içerik bağlama ikinci kez girmez.
7. **Kanıt özeti.** Issue'ya ham log değil, komut + exit code + dosya yolu +
   tek satır sonuç yazılır.
8. **Reviewer paketi.** Reviewer tüm repoyu değil, diff + AC + checklist +
   açık bulgular paketini okur. Fix sonrası yalnız delta diff yeniden incelenir.
9. **İstisna.** Güvenlik, ödeme, veri göçü ve geri dönüşü olmayan işlemlerde tam
   dosya okuma serbesttir; gerekçe evidence `notes` alanına yazılır.

## Uygulama

- Politika `delivery/registry.yaml → policies.context_budget` ile kayıtlıdır.
- `brief.py --cp` kompakt CP brief'i üretir; `orca_plan.py` worker spec'ine gömer.
- Bütçe ihlali bir kalite bulgusu değil, **duruş** nedenidir: özet yaz, yeni
  oturum aç, işi kaybetme.

## Done when

Yeni bir leaf'te worker bağlamı 200k token'ı geçmez; her CP `brief.py --cp`
çıktısıyla başlar ve `doctor.sh --strict` politikayı kayıtlı görür.
