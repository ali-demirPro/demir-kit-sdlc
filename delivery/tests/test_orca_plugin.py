"""Orca eklenti manifesti ve işçi sözleşmesi testleri (issue #180, CP-1)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "orca"
MANIFEST = PLUGIN / "orca-plugin.json"
WORKER = PLUGIN / "src" / "worker.ts"


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
        self.assertEqual(kinds, {"workspace:read", "storage:own", "settings:own"})

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


if __name__ == "__main__":
    unittest.main()
