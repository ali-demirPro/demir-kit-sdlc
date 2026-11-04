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

        self.assertEqual([event["on"] for event in contributes["events"]], ["workspace.changed"])

        settings = contributes["settings"]
        self.assertEqual(len(settings), 1)
        self.assertEqual(settings[0]["key"], "projectPath")
        self.assertEqual(settings[0]["type"], "string")

        kinds = {capability["kind"] for capability in manifest["capabilities"]}
        self.assertEqual(
            kinds, {"workspace:read", "workspace:write", "storage:own", "settings:own"}
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

    def test_no_mutation_calls(self) -> None:
        source = WORKER.read_text(encoding="utf-8")
        for forbidden in ("transition.sh", "seal", "claim", "git commit"):
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


class ReadOnlyTests(unittest.TestCase):
    """CP-3: eklenti salt-okunur kalır; yazma ve mutasyon aracı yoktur."""

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
            for forbidden in ("transition", "claim", "seal", "update.py"):
                self.assertNotIn(
                    forbidden,
                    source,
                    f"{path.relative_to(ROOT)}: {forbidden} geçiyor",
                )

    def test_no_repo_writes(self) -> None:
        for path in (WORKER, PANEL):
            source = path.read_text(encoding="utf-8")
            for forbidden in ("writeFile", "mkdir", "appendFile"):
                self.assertNotIn(
                    forbidden,
                    source,
                    f"{path.relative_to(ROOT)}: {forbidden} geçiyor",
                )

    def test_status_bar_calls(self) -> None:
        source = WORKER.read_text(encoding="utf-8")

        self.assertEqual(source.count("statusBar.update"), 2)
        self.assertIn("id: 'epic'", source)
        self.assertIn("id: 'cost'", source)


if __name__ == "__main__":
    unittest.main()
