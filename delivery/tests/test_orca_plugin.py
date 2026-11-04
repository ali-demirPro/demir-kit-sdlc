"""Orca eklenti manifesti, işçi sözleşmesi ve salt-okunur kanıtı (issue #180)."""

from __future__ import annotations

import json
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
        self.assertIn("`${CACHE_PREFIX}${ref.path}`", source)
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
        return source.split("function EpicDetail", 1)[1].split("function ProjectGroup", 1)[0]

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
        self.assertIn("const agentTarget =", worker)
        self.assertIn("deduped.some((project) => project.id === focused)", worker)
        self.assertIn("if (agentTarget !== null)", worker)
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
