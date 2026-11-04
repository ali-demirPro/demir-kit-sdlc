"""Tests for the read-only status CLI contract skeleton."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "delivery" / "scripts" / "status.py"

CONFIG = 'kit:\n  version: "0.0.0"\n'
TOP_LEVEL = {
    "contract_version",
    "generated_at",
    "stale",
    "source",
    "kit",
    "project",
    "epics",
    "counts",
    "warnings",
}

_STUB_TMP: tempfile.TemporaryDirectory[str] | None = None
DEFAULT_GH: Path | None = None


def setUpModule() -> None:
    """Varsayılan gh sahte: ağa çıkmadan başarısız olur."""
    global _STUB_TMP, DEFAULT_GH
    _STUB_TMP = tempfile.TemporaryDirectory(prefix="status-stub-")
    DEFAULT_GH = gh_stub(Path(_STUB_TMP.name) / "default", "echo 'gh yok' >&2\nexit 1\n")


def tearDownModule() -> None:
    if _STUB_TMP is not None:
        _STUB_TMP.cleanup()


def gh_stub(directory: Path, body: str) -> Path:
    """PATH'e konacak sahte `gh`; body kabuk gövdesi."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "gh"
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return directory


def gh_fixture(directory: Path, issues: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = directory / "issues.json"
    payload.write_text(json.dumps(issues), encoding="utf-8")
    return gh_stub(directory, f"cat {shlex.quote(str(payload))}\nexit 0\n")


def gh_marker(directory: Path, marker: Path) -> Path:
    """Çağrılırsa iz bırakan sahte gh."""
    return gh_stub(directory, f"echo called >> {shlex.quote(str(marker))}\nexit 1\n")


def doctor_stub(project: Path, log: Path, code: int = 0) -> None:
    """Proje içine sahte doctor.sh; her çağrıda issue numarasını loglar."""
    script = project / "delivery" / "scripts" / "doctor.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "#!/bin/sh\n" f"echo \"$2\" >> {shlex.quote(str(log))}\n" f"exit {code}\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def run(*args: str, cwd: Path, path: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    stub = path if path is not None else DEFAULT_GH
    if stub is not None:
        env["PATH"] = f"{stub}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


def project_dir(tmp: str) -> Path:
    project = Path(tmp) / "p"
    project.mkdir()
    (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
    return project


def issue(
    number: int,
    title: str,
    labels: tuple[str, ...] = (),
    body: str = "",
    state: str = "OPEN",
) -> dict:
    return {
        "number": number,
        "title": title,
        "state": state,
        "labels": [{"name": name} for name in labels],
        "body": body,
    }


EPIC_BODY = '```yaml demir-kit-epic\ndemir_kit_version: "2"\nchildren: [13, 14]\n```\n'
LEAF_BODY = """```yaml demir-kit
demir_kit_version: "2"
epic: 12
checkpoints:
  - {id: CP-1, title: bir}
  - {id: CP-2, title: iki}
```"""


class ContractTests(unittest.TestCase):
    def test_project_contract(self) -> None:
        proc = run("--json", "--offline", cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = payload(proc)
        self.assertEqual(set(data), TOP_LEVEL)
        self.assertEqual(data["contract_version"], 1)
        self.assertIsInstance(data["stale"], bool)
        self.assertEqual(data["source"], "live")
        self.assertRegex(data["generated_at"], r"^\d{4}-\d{2}-\d{2}T.*Z$")
        self.assertEqual(set(data["kit"]), {"version", "pin", "dirty"})
        self.assertIsInstance(data["kit"]["dirty"], (bool, type(None)))
        self.assertEqual(set(data["project"]), {"name", "profile", "repo_root", "tracker"})
        repo_root = data["project"]["repo_root"]
        self.assertTrue(repo_root is None or Path(repo_root).is_absolute())
        self.assertEqual(set(data["project"]["tracker"]), {"provider", "repo"})
        self.assertEqual(set(data["counts"]), {"epics", "leaves", "blocked"})
        self.assertTrue(all(isinstance(value, int) for value in data["counts"].values()))
        self.assertIsInstance(data["epics"], list)
        self.assertIsInstance(data["warnings"], list)


class CliTests(unittest.TestCase):
    # T-1 izi: seal bu kimliği adlandırır; gövde ContractTests ile aynı.
    test_project_contract = ContractTests.test_project_contract

    def test_project_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ornek-proje"
            project.mkdir()
            proc = run("--json", "--project", str(project), cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["project"]["name"], "ornek-proje")

            (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
            proc = run("--json", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["project"]["name"], "ornek-proje")

        with tempfile.TemporaryDirectory() as tmp:
            proc = run("--json", cwd=Path(tmp))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("proje", proc.stderr.lower())

        proc = run("--json", "--project", "/nonexistent-proje", cwd=ROOT)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("proje dizini yok", proc.stderr.lower())

    def test_read_only_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            project.mkdir()
            (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
            proc = run("--json", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((project / ".orchestration").exists())


class CacheTests(unittest.TestCase):
    def project(self, tmp: str) -> Path:
        project = Path(tmp) / "p"
        project.mkdir()
        (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
        return project

    def test_cache_written_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            first = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(first.returncode, 0, first.stderr)
            cache = project / ".orchestration" / "status-cache.json"
            self.assertTrue(cache.is_file())
            written = json.loads(cache.read_text(encoding="utf-8"))
            self.assertEqual(set(written), {"saved_at", "args", "data"})

            loaded = payload(first)
            data = written["data"]
            self.assertEqual(data["contract_version"], 1)
            self.assertEqual(loaded["source"], "live")

            second = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(second.returncode, 0, second.stderr)
            cached = payload(second)
            self.assertEqual(cached["source"], "cache")
            self.assertTrue(any("önbellek" in item for item in cached["warnings"]))

    def test_corrupt_cache_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            cache = project / ".orchestration" / "status-cache.json"
            cache.parent.mkdir(parents=True)
            cache.write_text('{"contract_version": 99}', encoding="utf-8")
            proc = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(set(data), TOP_LEVEL)
            self.assertEqual(data["source"], "live")
            self.assertEqual(data["contract_version"], 1)

    def test_shallow_cache_with_null_sections_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            cache = project / ".orchestration" / "status-cache.json"
            cache.parent.mkdir(parents=True)
            broken = {
                "contract_version": 1,
                "generated_at": "2026-01-01T00:00:00Z",
                "stale": False,
                "source": "cache",
                "kit": None,
                "project": None,
                "epics": [],
                "counts": {"epics": 0, "leaves": 0, "blocked": 0},
                "warnings": [],
            }
            cache.write_text(
                json.dumps({"args": {"with_gate": False, "with_cost": False, "full": False},
                            "data": broken}),
                encoding="utf-8",
            )
            proc = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["source"], "live")

            cache.write_text(
                json.dumps({"args": {"with_gate": False, "with_cost": False, "full": False},
                            "data": broken}),
                encoding="utf-8",
            )
            text = run("--cache-ttl", "60", cwd=project)
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("proje:", text.stdout)

    def test_cache_respects_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            run("--json", "--cache-ttl", "60", cwd=project)
            proc = run("--json", "--cache-ttl", "60", "--with-gate", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["source"], "live")
            self.assertTrue(any("--with-gate" in item for item in data["warnings"]))

    def test_expired_and_negative_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            cache = project / ".orchestration" / "status-cache.json"
            cache.parent.mkdir(parents=True)
            cache.write_text('{"args": {}, "data": {}}', encoding="utf-8")
            old = time.time() - 3600
            os.utime(cache, (old, old))
            proc = run("--json", "--cache-ttl", "60", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["source"], "live")

        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(tmp)
            proc = run("--json", "--cache-ttl", "-5", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("negatif", proc.stderr)
            self.assertFalse((project / ".orchestration").exists())


class OfflineTests(unittest.TestCase):
    def test_offline_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            fresh = run(
                "--json",
                "--cache-ttl",
                "60",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic", ("executing",), EPIC_BODY),
                        issue(13, "Leaf", ("agent-approved",), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(fresh.returncode, 0, fresh.stderr)
            self.assertEqual(payload(fresh)["source"], "live")

            cache = project / ".orchestration" / "status-cache.json"
            self.assertTrue(cache.is_file())
            old = time.time() - 3600
            os.utime(cache, (old, old))

            marker = Path(tmp) / "gh-called"
            offline = run(
                "--json",
                "--offline",
                cwd=project,
                path=gh_marker(Path(tmp) / "bin-offline", marker),
            )
            self.assertEqual(offline.returncode, 0, offline.stderr)
            self.assertFalse(marker.exists(), "offline modda gh çağrılmamalı")
            data = payload(offline)
            self.assertEqual(data["source"], "cache")
            self.assertFalse(data["stale"])
            self.assertEqual([epic["number"] for epic in data["epics"]], [12])
            self.assertIsNone(data["epics"][0]["gate"], "offline gate verisi uydurmamalı")
            self.assertEqual(data["counts"], {"epics": 1, "leaves": 1, "blocked": 0})

    def test_offline_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            marker = Path(tmp) / "gh-called"
            proc = run(
                "--json",
                "--offline",
                cwd=project,
                path=gh_marker(Path(tmp) / "bin", marker),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(marker.exists(), "offline modda gh çağrılmamalı")
            data = payload(proc)
            self.assertTrue(data["stale"])
            self.assertEqual(data["epics"], [])
            self.assertTrue(any("önbellek yok" in item for item in data["warnings"]))
            self.assertFalse((project / ".orchestration").exists())

    def test_offline_gate_not_replayed_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            log = Path(tmp) / "doctor.log"
            doctor_stub(project, log)
            stub = gh_fixture(
                Path(tmp) / "bin",
                [issue(12, "Epic", ("executing",), EPIC_BODY), issue(13, "Leaf", (), LEAF_BODY)],
            )
            warm = run("--json", "--with-gate", "--cache-ttl", "60", cwd=project, path=stub)
            self.assertEqual(warm.returncode, 0, warm.stderr)
            self.assertEqual(payload(warm)["epics"][0]["gate"], "pass")

            plain = run("--json", "--offline", cwd=project, path=stub)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            self.assertIsNone(payload(plain)["epics"][0]["gate"])

            gated = run("--json", "--offline", "--with-gate", cwd=project, path=stub)
            self.assertEqual(gated.returncode, 0, gated.stderr)
            self.assertEqual(payload(gated)["epics"][0]["gate"], "pass")

    def test_gh_failure_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_stub(Path(tmp) / "bin", "echo 'oturum yok' >&2\nexit 1\n"),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"], [])
            self.assertEqual(data["counts"], {"epics": 0, "leaves": 0, "blocked": 0})
            self.assertTrue(any("gh" in item.lower() for item in data["warnings"]))
            self.assertTrue(any("oturum yok" in item for item in data["warnings"]))
            self.assertTrue(data["stale"], "gh hatasında durum eksik sayılmalı")


class GateTests(unittest.TestCase):
    def test_gate_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            log = Path(tmp) / "doctor.log"
            doctor_stub(project, log)
            stub = gh_fixture(
                Path(tmp) / "bin",
                [
                    issue(12, "Epic", ("executing",), EPIC_BODY),
                    issue(13, "Leaf", (), LEAF_BODY),
                ],
            )

            plain = run("--json", cwd=project, path=stub)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            self.assertIsNone(payload(plain)["epics"][0]["gate"])
            self.assertFalse(log.exists(), "gate kapalıyken doctor çağrılmamalı")

            gated = run("--json", "--with-gate", cwd=project, path=stub)
            self.assertEqual(gated.returncode, 0, gated.stderr)
            self.assertEqual(payload(gated)["epics"][0]["gate"], "pass")
            self.assertEqual(log.read_text(encoding="utf-8").split(), ["12"])

    def test_gate_failure_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            log = Path(tmp) / "doctor.log"
            doctor_stub(project, log, code=1)
            proc = run(
                "--json",
                "--with-gate",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [issue(12, "Epic", (), EPIC_BODY), issue(13, "Leaf", (), LEAF_BODY)],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["epics"][0]["gate"], "fail")


class DataTests(unittest.TestCase):
    def test_epic_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic başlık", ("executing",), EPIC_BODY),
                        issue(13, "Leaf başlık", ("agent-approved",), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["counts"], {"epics": 1, "leaves": 1, "blocked": 0})
            epic = data["epics"][0]
            self.assertEqual(epic["number"], 12)
            self.assertEqual(epic["title"], "Epic başlık")
            self.assertEqual(epic["state"], "executing")
            self.assertIsNone(epic["risk"])
            self.assertEqual(epic["checkpoints"], {"done": 0, "total": 2})
            self.assertIsNone(epic["gate"])
            self.assertEqual(epic["open_findings"], 0)
            self.assertEqual(
                epic["approvals"], {"agent_approved": False, "human_qa": False}
            )
            self.assertIsNone(epic["next_action"])
            self.assertIsNone(epic["cycle_minutes"])
            self.assertIsNone(epic["cost_delta"])

    def test_state_priority_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(
                            12,
                            "Epic",
                            ("epic-reconcile", "blocked", "executing", "agent-approved", "human-qa"),
                            EPIC_BODY,
                        ),
                        issue(13, "Leaf", ("blocked",), LEAF_BODY),
                        issue(14, "Etiketsiz issue", (), ""),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["state"], "epic-reconcile")
            self.assertEqual(data["counts"], {"epics": 1, "leaves": 2, "blocked": 2})
            self.assertEqual(
                data["epics"][0]["approvals"],
                {"agent_approved": True, "human_qa": True},
            )

    def test_with_cost_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                "--with-cost",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [issue(12, "Epic", (), EPIC_BODY), issue(13, "Leaf", (), LEAF_BODY)],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertIsNone(data["epics"][0]["cost_delta"])
            self.assertTrue(any("maliyet" in item for item in data["warnings"]))


class ProgressTests(unittest.TestCase):
    def test_done_counts_leaf_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic", ("executing",), EPIC_BODY),
                        issue(13, "Biten leaf", ("leaf-done",), LEAF_BODY),
                        issue(14, "Açık leaf", ("agent-approved",), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            epic = payload(proc)["epics"][0]
            self.assertEqual(epic["checkpoints"], {"done": 2, "total": 4})

    def test_unfinished_children_contribute_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic", ("executing",), EPIC_BODY),
                        issue(13, "Açık leaf", ("agent-approved",), LEAF_BODY),
                        issue(14, "Açık leaf", ("agent-approved",), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            epic = payload(proc)["epics"][0]
            self.assertEqual(epic["checkpoints"], {"done": 0, "total": 4})


class StateTests(unittest.TestCase):
    def test_closed_issue_without_labels_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                "--all-epics",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [issue(12, "Epic", (), EPIC_BODY, state="CLOSED")],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(payload(proc)["epics"][0]["state"], "closed")


class ActiveEpicTests(unittest.TestCase):
    """CP-1: varsayılan yalnız aktif epic'ler; kapanmışlar gürültü yapmaz."""

    def test_done_epic_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            done = '```yaml demir-kit-epic\ndemir_kit_version: "2"\nchildren: [13]\n```\n'
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Aktif epic", ("executing",), EPIC_BODY),
                        issue(13, "Biten leaf", ("leaf-done",), LEAF_BODY),
                        issue(14, "Açık leaf", ("agent-approved",), LEAF_BODY),
                        issue(15, "Bitti epic", ("epic-done",), done),
                        issue(16, "Kapalı epic", (), done, state="CLOSED"),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual([epic["number"] for epic in data["epics"]], [12])
            self.assertEqual(data["counts"], {"epics": 1, "leaves": 2, "blocked": 0})
            # Kapalı epic'in çocuğu seal taşısa da listeye ve sayıma girmez.
            self.assertEqual(
                [leaf["number"] for leaf in data["epics"][0]["leaves"]], [13, 14]
            )

    def test_all_epics_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            done = '```yaml demir-kit-epic\ndemir_kit_version: "2"\nchildren: [13]\n```\n'
            stub = gh_fixture(
                Path(tmp) / "bin",
                [
                    issue(12, "Aktif epic", ("executing", "blocked"), EPIC_BODY),
                    issue(13, "Biten leaf", ("leaf-done",), LEAF_BODY),
                    issue(14, "Açık leaf", ("agent-approved", "blocked"), LEAF_BODY),
                    issue(15, "Bitti epic", ("epic-done",), done),
                    issue(16, "Kapalı epic", (), done, state="CLOSED"),
                ],
            )

            plain = run("--json", cwd=project, path=stub)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            # `blocked` kapanmış epic'lerin çocuklarını da saymaya devam eder.
            self.assertEqual(
                payload(plain)["counts"], {"epics": 1, "leaves": 2, "blocked": 2}
            )

            every = run("--json", "--all-epics", cwd=project, path=stub)
            self.assertEqual(every.returncode, 0, every.stderr)
            data = payload(every)
            self.assertEqual([epic["number"] for epic in data["epics"]], [12, 15, 16])
            self.assertEqual(data["counts"], {"epics": 3, "leaves": 4, "blocked": 2})
            self.assertEqual(data["epics"][1]["state"], "epic-done")
            self.assertEqual(data["epics"][2]["state"], "closed")


class LeafListTests(unittest.TestCase):
    def test_blocked_and_unsealed(self) -> None:
        """`blocked`/`deferred` öne geçer; seal'siz çocuk da listede görünür."""
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic", ("executing",), EPIC_BODY),
                        issue(13, "Engelli leaf", ("blocked", "executing"), LEAF_BODY),
                        issue(14, "Ertelenen leaf", ("deferred", "executing")),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            leaves = payload(proc)["epics"][0]["leaves"]
            self.assertEqual(
                leaves,
                [
                    {"number": 13, "title": "Engelli leaf", "state": "blocked"},
                    {"number": 14, "title": "Ertelenen leaf", "state": "deferred"},
                ],
            )

    def test_epic_leaves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic başlık", ("executing",), EPIC_BODY),
                        issue(13, "Biten leaf", ("leaf-done",), LEAF_BODY),
                        issue(14, "Açık leaf", ("agent-approved",), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            leaves = payload(proc)["epics"][0]["leaves"]
            self.assertEqual(
                leaves,
                [
                    {"number": 13, "title": "Biten leaf", "state": "leaf-done"},
                    {"number": 14, "title": "Açık leaf", "state": "agent-approved"},
                ],
            )

    def test_closed_issues_included(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic", ("executing",), EPIC_BODY),
                        issue(13, "Kapalı leaf", ("leaf-done",), LEAF_BODY, state="CLOSED"),
                        issue(14, "Açık leaf", (), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["counts"]["leaves"], 2)
            self.assertEqual(
                [leaf["number"] for leaf in data["epics"][0]["leaves"]], [13, 14]
            )


class RepoRootTests(unittest.TestCase):
    def test_repo_root(self) -> None:
        """Git deposunda ortak dizinin üstü; git yoksa `null`."""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git yok")
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            init = subprocess.run(
                ["git", "init", "-q", str(project)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            proc = run("--json", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                payload(proc)["project"]["repo_root"], str(project.resolve())
            )

        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run("--json", cwd=project)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIsNone(payload(proc)["project"]["repo_root"])


class VendoredKitTests(unittest.TestCase):
    def test_kit_in_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "urun"
            kit = project / "demir-kit"
            (kit / "delivery" / "scripts").mkdir(parents=True)
            (kit / "delivery" / "scripts" / "doctor.py").write_text("", encoding="utf-8")
            (kit / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            (project / "kit.config.yaml").write_text(
                'kit:\n  root: demir-kit\n  version: "9.9.9"\n', encoding="utf-8"
            )
            stub = gh_fixture(Path(tmp) / "gh", [])
            proc = run("--json", "--project", str(project), cwd=ROOT, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["kit"]["version"], "9.9.9")
            self.assertFalse(data["stale"])


class EndToEndTests(unittest.TestCase):
    def test_repo_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "gh-called"
            proc = run(
                "--json",
                "--offline",
                cwd=ROOT,
                path=gh_marker(Path(tmp) / "bin", marker),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(marker.exists(), "offline modda ağa çıkılmamalı")
            data = payload(proc)
            self.assertEqual(data["contract_version"], 1)
            self.assertEqual(set(data), TOP_LEVEL)
            self.assertTrue(data["kit"]["version"], "repo'da kit sürümü okunmalı")
            self.assertEqual(data["project"]["name"], "demir-kit")
            self.assertEqual(data["project"]["tracker"]["repo"], "ali-demirPro/demir-kit-sdlc")

    def test_epic_and_gate_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            log = Path(tmp) / "doctor.log"
            doctor_stub(project, log)
            stub = gh_fixture(
                Path(tmp) / "bin",
                [
                    issue(12, "Epic", ("executing",), EPIC_BODY),
                    issue(13, "Leaf", ("agent-approved",), LEAF_BODY),
                ],
            )
            proc = run("--json", "--with-gate", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["gate"], "pass")
            self.assertEqual(data["counts"], {"epics": 1, "leaves": 1, "blocked": 0})
            self.assertEqual(log.read_text(encoding="utf-8").split(), ["12"])

            text = run("--with-gate", cwd=project, path=stub)
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("epic 12:", text.stdout)


if __name__ == "__main__":
    unittest.main()
