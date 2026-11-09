"""Orca eklenti manifesti, işçi sözleşmesi ve salt-okunur kanıtı (issue #180)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "orca"
MANIFEST = PLUGIN / "orca-plugin.json"
WORKER = PLUGIN / "src" / "worker.ts"
PANEL = PLUGIN / "src" / "panel.tsx"
SOURCE_SUFFIXES = {".ts", ".tsx", ".json"}


class ManifestTests(unittest.TestCase):
    def test_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        contributes = manifest["contributes"]

        self.assertEqual(manifest["manifestVersion"], 2)
        self.assertEqual(manifest["id"], "demir-kit")
        self.assertEqual(manifest["name"], "demir-kit")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["execution"], "trusted-worker")
        self.assertEqual(manifest["main"], "src/worker.ts")
        self.assertEqual(manifest["engines"]["orca"], ">=1.4.248")

        panels = contributes["panels"]
        self.assertEqual(len(panels), 1)
        self.assertEqual(panels[0]["id"], "portfolio")
        self.assertEqual(panels[0]["entry"], "src/panel.tsx")
        self.assertEqual(panels[0]["ui"], "components")

        status_items = contributes["statusBarItems"]
        self.assertEqual(len(status_items), 2)
        self.assertEqual([item["id"] for item in status_items], ["epic", "cost"])
        self.assertEqual([item["icon"] for item in status_items], ["check", "gauge"])

        commands = contributes["commands"]
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["id"], "demir-kit.refresh")
        self.assertEqual(commands[0]["when"], "global")

        self.assertEqual(
            [event["on"] for event in contributes["events"]],
            ["workspace.changed", "agent.status.changed"],
        )

        settings = contributes["settings"]
        self.assertEqual(len(settings), 1)
        self.assertEqual(settings[0]["key"], "projectPath")
        self.assertEqual(settings[0]["type"], "string")

        kinds = {capability["kind"] for capability in manifest["capabilities"]}
        self.assertEqual(
            kinds,
            {"workspace:read", "workspace:write", "agent:read", "storage:own", "settings:own"},
        )

    def test_worker_contract(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        self.assertIn("status.py", source)
        self.assertIn("statusBar.update", source)
        self.assertIn("status.snapshot", source)
        # 30 saniyelik önbellek: süre sabiti ve depolama anahtarı birlikte.
        self.assertIn("CACHE_MS = 30_000", source)
        self.assertIn("saved_at", source)
        self.assertIn("workspace.changed", source)

    def test_mutation_only_through_kit_scripts(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        # CP-2: mutasyon yalnız kit scriptleriyle; doğrudan git/gh yazımı yok.
        self.assertIn("transition.sh", source)
        self.assertIn("next-leaf.sh", source)
        self.assertIn("'--claim'", source)
        for forbidden in ("git commit", "git push", "gh issue close", "gh pr merge", "seal"):
            self.assertNotIn(forbidden, source)


class WorkerBehaviorTests(unittest.TestCase):
    def test_cache_is_project_keyed(self) -> None:
        source = (PLUGIN / "src" / "worker.ts").read_text(encoding="utf-8")
        self.assertIn("CACHE_PREFIX = 'project:'", source)
        # Anahtar host dilimli ref: aynı yol iki hostta aynı girişe düşmez.
        self.assertIn("`${CACHE_PREFIX}${refKey(ref)}`", source)
        self.assertIn("cacheMatches(raw, ref)", source)
        self.assertIn("no-kit", source)

    def test_kit_root_is_confined(self) -> None:
        source = (PLUGIN / "src" / "worker.ts").read_text(encoding="utf-8")
        self.assertIn("includes('..')", source)


class MultiProjectTests(unittest.TestCase):
    """CP-2: her workspace ayrı okunur; hata ve önbellek proje başına kalır."""

    def test_partial_failure(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        # Projeler paralel okunur; biri patlarsa Promise.all düşmez.
        self.assertIn("Promise.all", source)
        # Hatalı proje kendi ok:false'u ile döner, diğer projeler ok:true kalır.
        self.assertIn("function failedProject", source)
        self.assertIn("ok: false", source)
        self.assertRegex(source, r"catch \(error\) \{\s*return failedProject\(")
        # Snapshot proje dizisi taşır; üst düzey hata yalnız kit yokken.
        self.assertIn("projects", source)
        self.assertIn("projects.some((project) => project.ok)", source)

    def test_click_goes_through_worker(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        worker = WORKER.read_text(encoding="utf-8")

        # Panel doğrudan host çağırmaz: istek `plugin.request` ile işçiye gider.
        self.assertIn(".request('workspace.open', { id: project.id })", panel)
        self.assertNotIn("host.call('workspace.open'", panel)
        # `workspace.open`'ı yalnız işçi çağırır ve `{ok}` sözlüğü döner.
        self.assertIn("orca.panels.handle('workspace.open'", worker)
        self.assertIn("'workspace.open', { workspaceId: raw }", worker)
        self.assertIn("return { ok: true }", worker)

    def test_dedupe_key(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        # İlk anahtar git kökü: ana checkout + epic worktree tek karta düşer.
        self.assertIn("project.repo_root", source)
        self.assertIn("root:${normalizePath(root)}", source)
        # Epic worktree son eki anahtardan atılır.
        self.assertIn("/\\/epic-\\d+$/", source)

    def test_status_bar_fallback(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        # Odaklı proje ok ve aktif epiği varsa EP satırı; yoksa sağlıklı sayı.
        self.assertIn("const epic = focused?.ok === true ? focused.epics?.[0] : undefined", source)
        self.assertIn("snapshot.projects.filter((item) => item.ok).length", source)
        self.assertIn("`${healthy} proje`", source)

    def test_status_text_short(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        self.assertIn("export function statusText", source)
        # Durum çubuğu biçimi sabit ve 64 karaktere kırpılır.
        self.assertRegex(
            source,
            r"return `EP-\$\{epic\.number\} · CP \$\{done\}/\$\{total\} · gate \$\{gate\}`\.slice\(0, 64\)",
        )
        # En uzun gerçekçi örnek bile sınırın altında.
        self.assertLessEqual(len("EP-99999 · CP 99/99 · gate fail"), 64)


class ActiveWorkTests(unittest.TestCase):
    """Panel gürültüsü düzeltmesi (#184): tek repo, aktif sayılar, boş proje."""

    def test_same_repo_listed_once(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        # Anahtar önce `repo_root`, sonra `tracker.repo`, yoksa normalize yol.
        self.assertIn("function projectKey", source)
        self.assertIn("repo_root", source)
        self.assertIn("tracker?.repo", source)
        self.assertIn("normalizePath", source)
        self.assertIn("dedupeProjects", source)
        # Aynı anahtar için odaklı ya da worktree olmayan yol kalır.
        self.assertIn("includes('/epic-')", source)
        self.assertIn("leftRank", source)
        self.assertIn("localeCompare", source)

    def test_panel_shows_active_counts(self) -> None:
        source = PANEL.read_text(encoding="utf-8")

        # Kart başlığı repo adı; altında tek satırda aktif epic/leaf sayısı.
        self.assertIn("function projectTitle", source)
        self.assertIn("function countsText", source)
        self.assertIn("`epic ${epics} · leaf ${leaves}`", source)
        # Aktif işi olmayan proje kartı gizlenmez, kısa satır gösterir.
        self.assertIn("açık iş yok", source)
        # Başlık biçimleri sabit: `#n — title` ve `#n — title · state`.
        self.assertIn("`#${epic.number} — ${epic.title ?? ''}`", source)
        self.assertIn(
            "`#${leaf.number} — ${leaf.title ?? ''} · ${leaf.state ?? '-'}`", source
        )


class PanelTests(unittest.TestCase):
    """CP-1: liste ve düz detay iki ayrı görünüm; detayda leaf listesi yok."""

    def detail_source(self) -> str:
        source = PANEL.read_text(encoding="utf-8")
        self.assertIn("function EpicDetail", source)
        return source.split("function EpicDetail", 1)[1].split("function isActive", 1)[0]

    def test_detail_is_flat(self) -> None:
        source = PANEL.read_text(encoding="utf-8")
        detail = self.detail_source()

        # Görünüm durumu: liste ya da proje+epic taşıyan detay.
        self.assertIn("const view = atom<PanelView>", source)
        self.assertIn("{ kind: 'detail'; projectId: string; epicNumber: number }", source)
        self.assertIn("{ kind: 'detail', projectId: project.id, epicNumber: epic.number }", source)
        # Detay tam panelde açılır ve geri düğmesi listeye döner.
        self.assertIn("‹ Geri", source)
        self.assertIn("set(view, { kind: 'list' })", source)
        # Düz detay: başlık, state/CP/onay rozetleri, next_action, kısa zaman.
        self.assertIn("epicTitle(epic)", detail)
        self.assertIn("cpText(epic)", detail)
        self.assertIn("next_action", detail)
        self.assertIn("shortTime", detail)
        # Detayda leaf listesi yok; leaf satırları yalnız liste görünümünde.
        self.assertNotIn("leaves", detail)
        list_source = source.split("function ProjectGroup", 1)[1].split("export default function Panel", 1)[0]
        self.assertIn("(epic.leaves ?? [])", list_source)


class EvaluationPanelTests(unittest.TestCase):
    """CP-2 (#310): eval özeti detayda tek satır; null güvenli, eski biçim uyumlu."""

    EVAL = PLUGIN / "src" / "eval.ts"
    EVAL_TEST = PLUGIN / "src" / "eval.test.ts"

    def sources(self) -> tuple[str, str, str, str]:
        return (
            PANEL.read_text(encoding="utf-8"),
            (PLUGIN / "src" / "protocol.ts").read_text(encoding="utf-8"),
            (PLUGIN / "src" / "panel.check.ts").read_text(encoding="utf-8"),
            self.EVAL.read_text(encoding="utf-8"),
        )

    @staticmethod
    def interface_block(protocol: str) -> str:
        """`PluginRequests` gövdesini kuyruğa taşmadan ayır (ADV-15)."""
        start = protocol.index("interface PluginRequests")
        opening = protocol.index("{", start)
        depth = 0
        for index in range(opening, len(protocol)):
            if protocol[index] == "{":
                depth += 1
            elif protocol[index] == "}":
                depth -= 1
                if depth == 0:
                    return protocol[opening : index + 1]
        raise AssertionError("PluginRequests bloğu kapanmadı")

    def test_eval_line_from_filled_fields(self) -> None:
        """T-4 / AC-2: saf yardımcı tek satır üretir; panel onu import eder."""
        panel, _, _, helper_source = self.sources()

        # Yardımcı ve taban kontrolleri saf modülde; panel kendi kopyasını taşımaz.
        self.assertNotIn("function evalText", panel)
        self.assertNotIn("function isCount", panel)
        self.assertIn("from './eval'", panel)
        self.assertIn("const evalLine = evalText(epic.evaluations)", panel)
        helper = helper_source.split("export function evalText", 1)[1].split(
            "export function", 1
        )[0]
        # ADV-13: sözleşme tabanı panelde de uygulanır; aralık dışı parça atlanır.
        self.assertIn("Number.isInteger(value) && value >= 0", helper_source)
        self.assertIn("value >= 0 && value <= 1", helper_source)
        # `eval P/T` iki sayı da doluysa; `discovery %N` yuvarlanır.
        self.assertIn("isCount(pass) && isCount(total)", helper)
        self.assertIn("`eval ${pass}/${total}`", helper)
        self.assertIn("isRate(rate)", helper)
        self.assertIn("Math.round(rate * 100)", helper)
        self.assertIn("isCount(count) && count > 0", helper)
        # ADV-12: bulgular sabit sırada; dizi ters çevrilirse test düşer.
        self.assertRegex(
            helper,
            r"\[\s*evaluations\.findings\?\.friction,\s*'friction'\s*\],\s*"
            r"\[\s*evaluations\.findings\?\.objection,\s*'objection'\s*\],\s*"
            r"\[\s*evaluations\.findings\?\.opportunity,\s*'opportunity'\s*\]",
        )
        # Hiçbir parça yoksa satır çizilmez: boş liste `null` döner.
        self.assertIn("parts.length === 0 ? null : parts.join(' · ')", helper)
        # Detay satırı yalnız doluysa çizilir; salt-okur Text.
        detail = panel.split("function EpicDetail", 1)[1].split("function isActive", 1)[0]
        self.assertIn("{evalLine !== null && (", detail)
        self.assertIn("{evalLine}", detail)

    def test_eval_outputs_are_executed(self) -> None:
        """ADV-11/12: node:test tam dizeyi ve kısmi null davranışını çalıştırır."""
        test_source = self.EVAL_TEST.read_text(encoding="utf-8")

        self.assertIn("from 'node:test'", test_source)
        self.assertIn("from './eval'", test_source)
        # Dolu ve sabit sıralı tam çıktı birebir iddia edilir.
        self.assertIn("'eval 12/14 · discovery %80 · 3 friction'", test_source)
        self.assertIn(
            "'eval 12/14 · discovery %80 · 1 friction · 2 objection · 3 opportunity'",
            test_source,
        )
        # Kısmi null: yalnız `3 friction`; sıfır bulgu ve all-null: satır yok.
        self.assertIn("'3 friction'", test_source)
        self.assertIn("'eval 12/14 · discovery %80'", test_source)
        self.assertIn("assert.equal(evalText(undefined), null)", test_source)
        self.assertIn("assert.equal(evalText(null), null)", test_source)

    def test_check_fixtures(self) -> None:
        """T-4: panel.check dolu, kısmi ve tümü null fixture'ları çizer."""
        _, _, check, _ = self.sources()

        # Dolu eval: `eval 12/14 · discovery %80 · 3 friction` üretir; 0 atlanır.
        self.assertIn("cases_pass: 12", check)
        self.assertIn("cases_total: 14", check)
        self.assertIn("discovery_rate: 0.8", check)
        self.assertIn("findings: { friction: 3, objection: 0, opportunity: 0 }", check)
        self.assertIn("detail:", check)
        # ADV-11: kısmi null fixture (epic 190) ve kendi senaryosu.
        partial = check.split("const partialEvaluationsEpic", 1)[1].split(
            "/** Eval kaydı yok", 1
        )[0]
        self.assertIn("number: 190", partial)
        self.assertIn("cases_pass: 12", partial)
        self.assertIn("cases_total: null", partial)
        self.assertIn("discovery_rate: null", partial)
        self.assertIn(
            "findings: { friction: 3, objection: null, opportunity: null }", partial
        )
        self.assertIn("evalPartial:", check)
        self.assertIn("epicNumber: 190", check)
        # Tümü null ikinci senaryo: satır çizilmez, çökme yok.
        self.assertIn("evalEmpty:", check)
        self.assertIn("epicNumber: 189", check)
        self.assertIn("cases_pass: null", check)

    def test_eval_empty_fixture_is_bound(self) -> None:
        """ADV-16: evalEmpty'in epic 189 + all-null bloğu snapshot'ta gerçekten durur."""
        _, _, check, _ = self.sources()

        empty = check.split("const emptyEvaluationsEpic", 1)[1].split(
            "const snapshot", 1
        )[0]
        self.assertIn("number: 189", empty)
        for field in (
            "batch: null",
            "cases_pass: null",
            "cases_total: null",
            "discovery_rate: null",
            "updated_at: null",
        ):
            self.assertIn(field, empty)
        self.assertIn(
            "findings: { friction: null, objection: null, opportunity: null }", empty
        )
        # Fixture snapshot'ın epics dizisinde: senaryo sessizce listeye düşmez.
        self.assertIn(
            "epics: [epicDetail, partialEvaluationsEpic, emptyEvaluationsEpic]", check
        )

    def test_legacy_without_evaluations(self) -> None:
        """T-5 / AC-3: alan opsiyonel; eski snapshot alanı taşımaz, panel çalışır."""
        panel, protocol, check, helper = self.sources()

        self.assertIn("export interface StatusEvaluations", protocol)
        self.assertIn("evaluations?: StatusEvaluations | null", protocol)
        for field in (
            "batch: string | null",
            "cases_pass: number | null",
            "cases_total: number | null",
            "discovery_rate: number | null",
            "updated_at: string | null",
        ):
            self.assertIn(field, protocol)
        for finding in ("friction: number | null", "objection: number | null", "opportunity: number | null"):
            self.assertIn(finding, protocol)
        # Eski `status.py` biçimi alanı taşımaz; legacy senaryosu korunur.
        legacy = check.split("const legacySnapshot", 1)[1].split("/** Aynı adlı", 1)[0]
        self.assertNotIn("evaluations", legacy)
        self.assertIn("legacy:", check)
        self.assertIn("epicNumber: 188", check)
        # ADV-14: tip sözleşmesi ve panel aynı hikâyeyi anlatır: `undefined`/`null`.
        self.assertIn("evaluations === undefined || evaluations === null", helper)
        self.assertIn("evalText(epic.evaluations)", panel)

    def test_read_only_no_new_request(self) -> None:
        """T-6 / AC-4: yeni plugin.request yok; panel yazma/ağ çağrısı yapmaz."""
        panel, protocol, _, _ = self.sources()

        expected = {"status.snapshot", "workspace.open", "epic.decision", "leaf.claim"}
        # ADV-15: çift tırnak, template literal ve alias çağrısı da yakalanır.
        names = set(re.findall(r"request\s*\(\s*['\"`]([^'\"`]+)", panel))
        self.assertEqual(names, expected)
        # `const ask = plugin.request` gibi alias yeni aksiyonu gizleyemez.
        self.assertNotRegex(panel, r"=\s*(?:await\s+)?plugin\s*\.\s*request(?!\s*\()")
        # Sözleşme aynı dört istekle sınırlı: yalnız arayüz gövdesi taranır.
        declared = set(re.findall(r"['\"]([^'\"]+)['\"]\s*:", self.interface_block(protocol)))
        self.assertEqual(declared, expected)
        # Panel yazma ya da ağ yolu açmaz; eval satırı düğme değil.
        for forbidden in ("writeFile", "appendFile", "mkdir", "fetch(", "fs."):
            self.assertNotIn(forbidden, panel)
        detail = panel.split("function EpicDetail", 1)[1].split("function isActive", 1)[0]
        self.assertIn("<Text muted size=\"xs\">", detail)


class ActionTests(unittest.TestCase):
    """CP-2: kabul/red/claim işçide kit scriptlerine gider; panel iki adım sorar."""

    def setUp(self) -> None:
        self.worker = WORKER.read_text(encoding="utf-8")
        self.panel = PANEL.read_text(encoding="utf-8")

    def test_accept_flow(self) -> None:
        self.assertIn("orca.panels.handle('epic.decision'", self.worker)
        self.assertIn("demir-kit-accept", self.worker)
        self.assertIn("decision: accepted", self.worker)
        self.assertIn("['api', 'user', '--jq', '.login']", self.worker)
        self.assertIn("'--to',", self.worker)
        self.assertIn("'epic-done',", self.worker)
        self.assertIn("'--accept',", self.worker)
        self.assertIn("['issue', 'comment', String(issue), '--body-file', temp.path]", self.worker)
        # Geçici dizin 0700, dosya 0600 ve iş sonunda silinir.
        self.assertIn("mkdtempSync(join(os.tmpdir(), 'demir-kit-'))", self.worker)
        self.assertIn("mode: 0o600", self.worker)
        self.assertIn("rmSync(dir, { recursive: true, force: true })", self.worker)
        # Geçiş düşerse az önce yazılan yorum URL'deki id ile silinir.
        self.assertIn("#issuecomment-(\\d+)", self.worker)
        self.assertIn("'api', '-X', 'DELETE'", self.worker)
        self.assertIn("repos/${match[1]}/issues/comments/${id}", self.worker)
        self.assertIn("'geçiş başarısız; yorum geri alındı'", self.worker)
        self.assertIn("'geçiş başarısız; yorum kaldı'", self.worker)
        # Proje snapshot'taki `path` ile eşleşir; belirsizlik yok.
        self.assertIn("function projectAt", self.worker)
        self.assertIn("function projectPathOf", self.worker)
        # Panel yalnız ister; işçi `{ok,message,exitCode,tail,url}` döner.
        protocol = (PLUGIN / "src" / "protocol.ts").read_text(encoding="utf-8")
        for field in ("ok: boolean", "message: string", "exitCode: number", "tail: string", "url: string"):
            self.assertIn(field, protocol)
        self.assertIn("label=\"Kabul et\"", self.panel)
        self.assertIn("projectPath", self.panel)
        # Hata UX: başarısız aksiyonda tail ve issue linki çizilir.
        self.assertIn("note.tail", self.panel)
        self.assertIn("openIssue(note.url)", self.panel)

    def test_success_returns_to_list(self) -> None:
        # Başarılı aksiyon detayı bırakır: liste görünümü + tazelenmiş snapshot.
        start = self.panel.index("async function runAction")
        run = self.panel[start:].split("function ActionNote", 1)[0]
        self.assertIn("if (reply.ok)", run)
        self.assertIn("set(view, { kind: 'list' })", run)
        self.assertIn("await refresh()", run)
        # Başarısız aksiyon detayda kalır: not, tail ve issue linki durur.
        self.assertIn("set(actionNote, reply)", run)
        self.assertNotIn("kind: 'detail'", run)
        self.assertIn("note.tail", self.panel)
        self.assertIn("openIssue(note.url)", self.panel)
        # Panelin kendi tazeleme yolu tek yerde: açılış, zamanlayıcı, düğme.
        self.assertIn("async function refresh", self.panel)
        self.assertIn("void refresh()", self.panel)

    def test_close_issue(self) -> None:
        # Kabul geçişinden sonra issue kapatılır; kapatma düşerse geçiş korunur.
        self.assertIn(
            "['issue', 'close', String(issue), '--reason=completed']", self.worker
        )
        self.assertIn("`issue kapatılamadı: ${reason}`", self.worker)
        self.assertRegex(
            self.worker,
            r"return actionReply\(\s*true,\s*'epic kabul edildi',\s*0,\s*transition,\s*url,\s*`issue kapatılamadı",
        )
        # Yan adım geçişin arkasındadır; red dalı kapatmaz.
        transition_at = self.worker.index("'--to',")
        close_at = self.worker.index("['issue', 'close'")
        reject_at = self.worker.index("if (decision === 'rejected')")
        self.assertLess(reject_at, transition_at)
        self.assertLess(transition_at, close_at)
        # `warning` isteğe bağlı alan; panel onu uyarı kutusunda gösterir.
        protocol = (PLUGIN / "src" / "protocol.ts").read_text(encoding="utf-8")
        self.assertIn("warning?: string", protocol)
        self.assertIn("note.warning", self.panel)

    def test_reject_flow(self) -> None:
        self.assertIn("decision: rejected", self.worker)
        # AC-4: red yalnız yorum yazar; `--to blocked` geçişi yok.
        self.assertNotIn("'--reason'", self.worker)
        self.assertNotIn("insan reddetti", self.worker)
        # Red dalı, transition çağrısından önce döner.
        reject_at = self.worker.index("if (decision === 'rejected')")
        transition_at = self.worker.index("'transition.sh'")
        self.assertLess(reject_at, transition_at)
        self.assertIn("label=\"Reddet\"", self.panel)

    def test_claim_flow(self) -> None:
        self.assertIn("orca.panels.handle('leaf.claim'", self.worker)
        self.assertIn("'next-leaf.sh'", self.worker)
        self.assertIn("[script, '--claim']", self.worker)
        # Claim proje kartında: istek yalnız `{projectPath}` taşır.
        self.assertIn("label=\"Sıradaki leaf'i claim et\"", self.panel)
        self.assertIn(
            "plugin.request('leaf.claim', { projectPath: project.path })",
            self.panel,
        )
        self.assertNotIn("'leaf.claim', { issue:", self.panel)
        # İki adımlı onay: ilk tık sorar, ikinci tık çağırır.
        self.assertIn("Emin misin?", self.panel)
        self.assertIn("Vazgeç", self.panel)
        self.assertIn("set(confirm, { id })", self.panel)

    def test_gate_labels(self) -> None:
        # Yorum yazmadan önce etiketler `gh issue view` ile okunur.
        self.assertIn("['issue', 'view', String(issue), '--json', 'labels']", self.worker)
        self.assertIn("function checkGate", self.worker)
        self.assertIn("'human-qa'", self.worker)
        self.assertIn("'agent-approved'", self.worker)
        self.assertIn("'executing'", self.worker)
        self.assertIn("'leaf-done'", self.worker)
        # Kapı düşerse `{ok:false}` döner, yorum yazılmaz.
        self.assertIn("if (!gate.ok)", self.worker)
        self.assertIn("gate.reason,", self.worker)


class LiveTests(unittest.TestCase):
    """CP-2: canlı ajan durumu ve tıklanınca açılan detay."""

    def test_agents_event(self) -> None:
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("agent.status.changed", source)
        self.assertIn("agents.list", source)
        self.assertIn("live", source)

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn(
            "agent:read", {item["kind"] for item in manifest["capabilities"]}
        )

    def test_detail_renders(self) -> None:
        source = PANEL.read_text(encoding="utf-8")
        self.assertIn("checkpoints", source)
        self.assertIn("openExternal", source)
        self.assertIn("Issue'yu aç", source)


class ReviewFixTests(unittest.TestCase):
    """#187 review: eski şekil çökmez, ajan atfı odaklı, CP satırı leaf taşır."""

    def test_old_checkpoint_shape_does_not_crash(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        worker = WORKER.read_text(encoding="utf-8")

        # Dizi olmayan `{done,total}` boş liste sayılır; iki dosyada da.
        self.assertGreaterEqual(
            panel.count("Array.isArray(epic.checkpoints) ? epic.checkpoints : []"), 2
        )
        self.assertIn("Array.isArray(epic.checkpoints) ? epic.checkpoints : []", worker)
        # Önbellek doğrulaması eski şekli reddetmez (crash yok).
        self.assertIn("function isCheckpoints", worker)
        self.assertIn("function isEpic", worker)
        self.assertIn("total", worker)
        # `orca plugin check` eski şekilli sahte snapshot'ı da çizer.
        check = (PLUGIN / "src" / "panel.check.ts").read_text(encoding="utf-8")
        self.assertIn("legacy:", check)
        self.assertIn("checkpoints: { done: 1, total: 2 }", check)

    def test_agents_only_for_focused_project(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        # Odaklı workspace kit taşımıyorsa hiçbir karta ajan yazılmaz.
        self.assertIn("export function agentTarget", worker)
        self.assertIn("const target = agentTarget(deduped, snapshots, focused)", worker)
        # Yapısal değişmez: ajanlar yalnız hedef kartın dalında yazılır, kalan
        # kartlar boş liste ve sıfır sayaçla döner.
        self.assertIn("project.id === target", worker)
        self.assertIn(
            "{ ...project, agents: listing.agents, live: listing.live }", worker
        )
        self.assertIn(": { ...project, agents: [], live: zeroLive() }", worker)
        self.assertIn("live[agent.state] += 1", worker)
        # CP-2: olay hedefi saf yardımcıyla seçilir; workspace yoksa tam tazeleme.
        self.assertIn("export function agentEventTarget", worker)
        self.assertIn(
            "agentEventTarget(workspaceIdOf(event), lastAgentWorkspace)", worker
        )
        # Olayın workspaceId'si varsa yalnız o kart tazelenir.
        self.assertIn("function workspaceIdOf", worker)
        self.assertIn("function refreshAgents", worker)
        self.assertIn("if (target !== lastAgentWorkspace) return", worker)

    def test_checkpoint_carries_leaf(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        status = (ROOT / "delivery" / "scripts" / "status.py").read_text(encoding="utf-8")

        self.assertIn('"leaf": leaf', status)
        self.assertIn("#${checkpoint.leaf} · ${checkpoint.id}", panel)

    def test_idle_agent_counted(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn("'idle'", worker)
        self.assertIn("idle: 0", worker)
        self.assertIn("boşta", panel)


class FocusPersistenceTests(unittest.TestCase):
    """Kalıcı odak: terminal eşlemesi, TTL/LRU temizliği ve hatasız snapshot."""

    def test_focus_signals(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        # Üç sinyal: olay/id-yol, kalıcı terminal haritası, odaklı ajan terminali.
        self.assertIn("export function resolveFocus", worker)
        self.assertIn("export function hintsFromWorkspaceId", worker)
        self.assertIn("export function matchWorkspaceHint", worker)
        self.assertIn("export function terminalFocus", worker)
        self.assertIn("agentTerminals", worker)
        # Orca 1.4.248 olayı `worktreeId` taşır; terminal id'si boş olabilir.
        self.assertIn("export function agentWorkspaceHint", worker)
        self.assertIn("payload.worktreeId", worker)
        self.assertIn("export function activeAgentFocus", worker)
        self.assertIn("stateStartedAt", worker)
        # İç worktree id'si (`<repo>::/yol`) yol olarak çözülür.
        self.assertIn("text.indexOf('::')", worker)
        self.assertIn("text.startsWith('identity:')", worker)

    def test_storage_is_bounded_and_pruned(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")

        self.assertIn("TERMINAL_MAP_LIMIT = 200", worker)
        self.assertIn("TERMINAL_TTL_MS = 30 * 24 * 60 * 60 * 1000", worker)
        self.assertIn("TERMINAL_STORE_KEY = 'agents.terminals.v1'", worker)
        self.assertIn("export function pruneTerminalMap", worker)
        self.assertIn("!truncated && workspaces.length > 0", worker)
        self.assertIn("orca.storage.delete(TERMINAL_STORE_KEY)", worker)
        # Kayıt yalnız değiştiyse ve 1 sn debounce ile yazılır.
        self.assertIn("TERMINAL_SAVE_MS = 1000", worker)
        self.assertIn("scheduleTerminalSave", worker)

    def test_snapshot_never_throws(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        panel = PANEL.read_text(encoding="utf-8")

        self.assertIn("function errorSnapshot", worker)
        self.assertIn("orca.panels.handle('status.snapshot'", worker)
        self.assertIn("return lastSnapshot ?? errorSnapshot", worker)
        self.assertIn("function focusNotice", panel)
        self.assertIn("odak çözülemedi", panel)
        # Odak çözülmedi diye kırmızı hata kutusu çizilmez.
        self.assertNotIn("Odak çözülemedi\" icon=\"error", panel)

    def test_snapshot_carries_live_and_active(self) -> None:
        protocol = (PLUGIN / "src" / "protocol.ts").read_text(encoding="utf-8")
        worker = WORKER.read_text(encoding="utf-8")
        panel = PANEL.read_text(encoding="utf-8")

        for field in ("focusSource?:", "live?:", "active?:", "stateStartedAt?:"):
            self.assertIn(field, protocol)
        self.assertIn("export function activeOf", worker)
        self.assertIn("live: listing.live", worker)
        self.assertIn("active,", worker)
        # Durum çubuğu odak epic'i yoksa ilk yürüyen epic'i gösterir.
        self.assertIn("function firstActiveEpic", worker)
        self.assertIn("function epicLine", worker)
        # Odak olmayan yürüyen proje "aktif" rozeti alır.
        self.assertIn("function isActive", panel)
        self.assertIn('<Badge tone="accent">aktif</Badge>', panel)


class ReadOnlyTests(unittest.TestCase):
    """CP-2: mutasyon yalnız kit scriptleriyle; panel repoya yazmaz."""

    def plugin_sources(self) -> list[Path]:
        return sorted(
            path
            for path in PLUGIN.rglob("*")
            if path.is_file() and path.suffix in SOURCE_SUFFIXES
        )

    def test_no_mutation_tools(self) -> None:
        sources = self.plugin_sources()
        self.assertGreaterEqual(len(sources), 5)

        for path in sources:
            source = path.read_text(encoding="utf-8")
            # Doğrudan ajan/mutasyon aracı yok: yalnız kit scriptleri çağrılır.
            for forbidden in ("git commit", "git push", "gh issue close", "gh pr merge", "update.py"):
                self.assertNotIn(
                    forbidden,
                    source,
                    f"{path.relative_to(ROOT)}: {forbidden} geçiyor",
                )

    def test_no_repo_writes(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        panel = PANEL.read_text(encoding="utf-8")

        # Kabul/red yorumu 0700 geçici dizin + 0600 dosyaya yazılır; repoya yazma yok.
        self.assertIn("os.tmpdir()", worker)
        self.assertIn("mkdtempSync(join(os.tmpdir(), 'demir-kit-'))", worker)
        self.assertIn("writeFileSync(path, body, { encoding: 'utf8', mode: 0o600 })", worker)
        self.assertIn("removeTempDir", worker)
        for forbidden in ("writeFileSync(join(ref.path", "writeFileSync(join(project", "mkdir"):
            self.assertNotIn(forbidden, worker)
        for forbidden in ("writeFile", "mkdir", "appendFile"):
            self.assertNotIn(forbidden, panel)

    def test_status_bar_calls(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        self.assertEqual(source.count("statusBar.update"), 2)
        self.assertIn("id: 'epic'", source)
        self.assertIn("id: 'cost'", source)


if __name__ == "__main__":
    unittest.main()
