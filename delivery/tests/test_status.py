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
import unittest.mock
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
    "pulse",
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


def gh_split(
    directory: Path,
    meta: list[dict],
    open_rows: list[dict],
    labeled_rows: list[dict],
    log: Path,
    bytes_log: Path,
) -> Path:
    """İki aşamalı çekimi taklit eden sahte gh.

    `--state all` gövdesiz özeti, `--state open` açık gövdeleri, `-no:label`
    araması kapalı-etiketli gövdeleri döner; çağrılan args'ı `log`a, indirilen
    bayt sayısını `bytes_log`a yazar.
    """
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "--state all": meta,
        "--state open": open_rows,
        "-no:label": labeled_rows,
    }
    files: dict[str, Path] = {}
    for key, rows in payloads.items():
        payload = directory / f"{len(files)}.json"
        payload.write_text(json.dumps(rows), encoding="utf-8")
        files[key] = payload
    q = shlex.quote
    body = (
        f"echo \"$@\" >> {q(str(log))}\n"
        "case \"$*\" in\n"
        f"  *\"--state open\"*) f={q(str(files['--state open']))} ;;\n"
        f"  *\"-no:label\"*) f={q(str(files['-no:label']))} ;;\n"
        f"  *\"--state all\"*) f={q(str(files['--state all']))} ;;\n"
        "  *) echo 'beklenmeyen args: '\"$*\" >&2; exit 2 ;;\n"
        "esac\n"
        f"wc -c < \"$f\" >> {q(str(bytes_log))}\n"
        "cat \"$f\"\n"
        "exit 0\n"
    )
    return gh_stub(directory, body)


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
    updated_at: str | None = None,
) -> dict:
    data = {
        "number": number,
        "title": title,
        "state": state,
        "labels": [{"name": name} for name in labels],
        "body": body,
    }
    if updated_at is not None:
        data["updatedAt"] = updated_at
    return data


EPIC_BODY = '```yaml demir-kit-epic\ndemir_kit_version: "2"\nchildren: [13, 14]\n```\n'
LEAF_BODY = """```yaml demir-kit
demir_kit_version: "2"
epic: 12
checkpoints:
  - {id: CP-1, title: bir}
  - {id: CP-2, title: iki}
```"""

EVALUATION_KEYS = {
    "batch",
    "cases_pass",
    "cases_total",
    "discovery_rate",
    "findings",
    "updated_at",
}
FINDING_KEYS = {"friction", "objection", "opportunity"}
NULL_EVALUATIONS = {
    "batch": None,
    "cases_pass": None,
    "cases_total": None,
    "discovery_rate": None,
    "findings": {"friction": None, "objection": None, "opportunity": None},
    "updated_at": None,
}


def write_evaluations(project: Path, payload: object) -> Path:
    path = project / ".kit" / "evaluations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def evaluations_doc(epics: dict) -> dict:
    return {"demir_kit_version": "2", "epics": epics}


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


class FetchTests(unittest.TestCase):
    """T-1 / T-2: iki aşamalı indirme; 500 sınırı hata olur."""

    def fixture_277(self) -> list[dict]:
        filler = "g" * 2400
        rows = [
            issue(
                1,
                "Epic 361",
                ("executing",),
                EPIC_BODY + filler,
                state="OPEN",
                updated_at="2026-11-01T00:00:00Z",
            ),
        ]
        for n in range(2, 9):
            rows.append(
                issue(
                    n,
                    f"Leaf {n}",
                    ("executing",),
                    LEAF_BODY + filler,
                    state="OPEN",
                    updated_at="2026-11-01T00:00:00Z",
                )
            )
        for n in range(10, 30):
            rows.append(
                issue(
                    n,
                    f"Biten {n}",
                    ("leaf-done",),
                    LEAF_BODY + filler,
                    state="CLOSED",
                    updated_at="2026-10-01T00:00:00Z",
                )
            )
        for n in range(30, 279):
            rows.append(
                issue(
                    n,
                    f"Eski {n}",
                    (),
                    "gövde: " + filler,
                    state="CLOSED",
                    updated_at="2026-09-01T00:00:00Z",
                )
            )
        return rows

    # T-1: gövde yalnız açık/etiketli issue'lar için istenir; çıktı ≤ 300 KB.
    def test_t1_body_only_for_open_and_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            rows = self.fixture_277()
            self.assertEqual(len(rows), 277)
            meta = [{k: v for k, v in row.items() if k != "body"} for row in rows]
            open_rows = [row for row in rows if row["state"] == "OPEN"]
            labeled = [
                row for row in rows if row["state"] != "OPEN" and row["labels"]
            ]
            log = Path(tmp) / "calls.log"
            bytes_log = Path(tmp) / "bytes.log"
            stub = gh_split(Path(tmp) / "bin", meta, open_rows, labeled, log, bytes_log)
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = log.read_text(encoding="utf-8").splitlines()
            body_calls = [call for call in calls if "body" in call]
            self.assertTrue(body_calls, "gövde hiç istenmedi")
            for call in body_calls:
                self.assertTrue(
                    "--state open" in call or "-no:label" in call,
                    f"gövde beklenmeyen çağrıda istendi: {call}",
                )
            for call in calls:
                if "--state all" in call:
                    self.assertNotIn("body", call)
            total = sum(int(line) for line in bytes_log.read_text(encoding="utf-8").split())
            self.assertLessEqual(
                total, 300 * 1024, f"indirilen JSON {total} bayt (≤ 300 KB olmalı)"
            )
            data = payload(proc)
            self.assertTrue(any(epic["number"] == 1 for epic in data["epics"]))

    # T-2: 500 kayıt dönen gh, çıkış 1 + stale nedeni üretir.
    def test_t2_limit_is_error_not_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            rows = [
                issue(
                    n,
                    f"İssue {n}",
                    ("intake",),
                    f"gövde {n}",
                    updated_at="2026-11-01T00:00:00Z",
                )
                for n in range(1, 501)
            ]
            stub = gh_fixture(Path(tmp) / "bin", rows)
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            data = payload(proc)
            self.assertTrue(data["stale"])
            self.assertEqual(data["epics"], [])
            self.assertTrue(
                any("500" in item for item in data["warnings"]),
                data["warnings"],
            )
            plain = run(cwd=project, path=stub)
            self.assertEqual(plain.returncode, 1)
            self.assertIn("500", plain.stdout)


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
            self.assertEqual(
                epic["checkpoints"],
                [
                    {"id": "CP-1", "title": "bir", "done": False, "leaf": 13},
                    {"id": "CP-2", "title": "iki", "done": False, "leaf": 13},
                ],
            )
            self.assertIsNone(epic["updated_at"])
            self.assertIsNone(epic["url"])
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


class EvaluationsTests(unittest.TestCase):
    """CP-1: `.kit/evaluations.json` salt-okur sözleşmesi."""

    RECORD = {
        "batch": "batch-7",
        "cases_pass": 12,
        "cases_total": 14,
        "discovery_rate": 0.8,
        "findings": {"friction": 3, "objection": 0, "opportunity": 0},
        "updated_at": "2026-11-09T10:00:00Z",
    }

    def setup_project(
        self, tmp: str, payload: object | None = None
    ) -> tuple[Path, Path]:
        project = project_dir(tmp)
        if payload is not None:
            write_evaluations(project, payload)
        stub = gh_fixture(
            Path(tmp) / "bin",
            [
                issue(12, "Epic", ("executing",), EPIC_BODY),
                issue(13, "Leaf", ("agent-approved",), LEAF_BODY),
            ],
        )
        return project, stub

    def epic_of(self, proc: subprocess.CompletedProcess[str]) -> dict:
        return payload(proc)["epics"][0]

    def test_t1_file_values_and_types(self) -> None:
        """T-1: dosya okunur; tüm alanlar doğru değer ve tipte çıkar."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            block = self.epic_of(proc)["evaluations"]
            self.assertEqual(set(block), EVALUATION_KEYS)
            self.assertEqual(block, self.RECORD)
            self.assertIsInstance(block["batch"], str)
            self.assertIsInstance(block["cases_pass"], int)
            self.assertIsInstance(block["cases_total"], int)
            self.assertIsInstance(block["discovery_rate"], float)
            self.assertEqual(set(block["findings"]), FINDING_KEYS)
            self.assertTrue(
                all(isinstance(value, int) for value in block["findings"].values())
            )
            self.assertEqual(block["updated_at"], "2026-11-09T10:00:00Z")

    def test_t2_missing_file_is_all_null(self) -> None:
        """T-2: dosya yok → alanlar null; sıfır uydurulmaz."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp)
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(self.epic_of(proc)["evaluations"], NULL_EVALUATIONS)

    def test_t2_corrupt_file_warns(self) -> None:
        """T-2: bozuk JSON → null + uyarı; komut çökmez."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp, "{bozuk json")
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)
            self.assertTrue(any("evaluations" in item for item in data["warnings"]))

    def test_t2_invalid_fields_null_with_warnings(self) -> None:
        """T-2: eksik/yanlış tip/aralık dışı alan null + uyarı; sıfır yok."""
        with tempfile.TemporaryDirectory() as tmp:
            broken = {
                "batch": 7,
                "cases_pass": -1,
                "cases_total": "14",
                "discovery_rate": 1.5,
                "findings": {"friction": -2, "objection": "0"},
                "updated_at": "dün",
            }
            project, stub = self.setup_project(tmp, evaluations_doc({"12": broken}))
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)
            field_warnings = [
                item for item in data["warnings"] if item.startswith("evaluations 12:")
            ]
            self.assertGreaterEqual(len(field_warnings), 6, field_warnings)

    def test_t2_explicit_nulls_are_valid(self) -> None:
        """T-2: açık `null` geçerli; uyarı üretmez, sıfıra çevrilmez."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": NULL_EVALUATIONS})
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)
            self.assertFalse(
                any(item.startswith("evaluations") for item in data["warnings"]),
                data["warnings"],
            )

    def test_t2_missing_fields_warn(self) -> None:
        """T-2: eksik alan null + uyarı; kayıt nesne değilse de çökmez."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": {"batch": "batch-7"}, "13": "bozuk"})
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"]["batch"], "batch-7")
            self.assertEqual(
                data["epics"][0]["evaluations"]["cases_pass"], None
            )
            self.assertTrue(
                any("evaluations 12:" in item for item in data["warnings"])
            )
            self.assertTrue(
                any("evaluations 13:" in item for item in data["warnings"])
            )

    def test_t3_existing_fields_and_text_output(self) -> None:
        """T-3: mevcut alanlar aynı ad/tip; düz metin çıktısı değişmez."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            epic = self.epic_of(proc)
            self.assertEqual(
                set(epic),
                {
                    "number",
                    "title",
                    "state",
                    "risk",
                    "checkpoints",
                    "updated_at",
                    "url",
                    "leaves",
                    "gate",
                    "open_findings",
                    "approvals",
                    "next_action",
                    "cycle_minutes",
                    "machinery",
                    "cost_delta",
                    "evaluations",
                },
            )
            self.assertIsInstance(epic["number"], int)
            self.assertIsInstance(epic["title"], str)
            self.assertIsInstance(epic["state"], str)
            self.assertIsNone(epic["risk"])
            self.assertIsInstance(epic["checkpoints"], list)
            self.assertIsNone(epic["updated_at"])
            self.assertIsNone(epic["url"])
            self.assertIsInstance(epic["leaves"], list)
            self.assertIsNone(epic["gate"])
            self.assertIsInstance(epic["open_findings"], int)
            self.assertEqual(set(epic["approvals"]), {"agent_approved", "human_qa"})
            self.assertTrue(all(isinstance(v, bool) for v in epic["approvals"].values()))
            self.assertIsNone(epic["next_action"])
            self.assertIsNone(epic["cycle_minutes"])
            self.assertIsNone(epic["cost_delta"])

            text = run(cwd=project, path=stub)
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("epic 12:", text.stdout)
            self.assertNotIn("evaluations", text.stdout)

    def test_t3_offline_cache_keeps_evaluations(self) -> None:
        """T-3: `--offline` önbellekten aynı evaluations bloğunu döner."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            warm = run("--json", "--cache-ttl", "60", cwd=project, path=stub)
            self.assertEqual(warm.returncode, 0, warm.stderr)
            offline = run("--json", "--offline", cwd=project, path=stub)
            self.assertEqual(offline.returncode, 0, offline.stderr)
            data = payload(offline)
            self.assertEqual(data["source"], "cache")
            self.assertFalse(data["stale"])
            self.assertEqual([epic["number"] for epic in data["epics"]], [12])
            self.assertEqual(data["epics"][0]["evaluations"], self.RECORD)

    def test_t3_old_cache_without_evaluations_is_accepted(self) -> None:
        """ADV-4: evaluations taşımayan eski önbellek all-null blokla kabul edilir."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            first = run("--json", "--cache-ttl", "60", cwd=project, path=stub)
            self.assertEqual(first.returncode, 0, first.stderr)
            cache = project / ".orchestration" / "status-cache.json"
            envelope = json.loads(cache.read_text(encoding="utf-8"))
            for epic in envelope["data"]["epics"]:
                epic.pop("evaluations", None)
            cache.write_text(json.dumps(envelope), encoding="utf-8")

            second = run("--json", "--cache-ttl", "60", cwd=project, path=stub)
            self.assertEqual(second.returncode, 0, second.stderr)
            data = payload(second)
            self.assertEqual(data["source"], "cache")
            self.assertEqual([epic["number"] for epic in data["epics"]], [12])
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)

    def test_adv4_offline_serves_legacy_cache(self) -> None:
        """ADV-4: `--offline` eski (evaluations'sız) önbellekten epic'leri korur."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            warm = run("--json", "--cache-ttl", "60", cwd=project, path=stub)
            self.assertEqual(warm.returncode, 0, warm.stderr)
            cache = project / ".orchestration" / "status-cache.json"
            envelope = json.loads(cache.read_text(encoding="utf-8"))
            for epic in envelope["data"]["epics"]:
                epic.pop("evaluations", None)
            cache.write_text(json.dumps(envelope), encoding="utf-8")

            offline = run("--json", "--offline", cwd=project, path=stub)
            self.assertEqual(offline.returncode, 0, offline.stderr)
            data = payload(offline)
            self.assertEqual(data["source"], "cache")
            self.assertFalse(data["stale"])
            self.assertEqual([epic["number"] for epic in data["epics"]], [12])
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)

    def test_adv1_invalid_utf8_is_null(self) -> None:
        """ADV-1: geçersiz UTF-8 çökmez; null + uyarı, exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp)
            path = project / ".kit" / "evaluations.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'{"epics": {"12": {"batch": "\xff\xfe"}}}')
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)
            self.assertTrue(
                any("JSON geçersiz" in item for item in data["warnings"]),
                data["warnings"],
            )

    def test_adv2_huge_rate_in_file_is_null(self) -> None:
        """ADV-2: 10**400 discovery_rate OverflowError değil, null + uyarı."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp)
            path = project / ".kit" / "evaluations.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '{"demir_kit_version": "2", "epics": {"12": '
                '{"discovery_rate": ' + str(10**400) + "}}}",
                encoding="utf-8",
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertIsNone(data["epics"][0]["evaluations"]["discovery_rate"])
            self.assertTrue(
                any("discovery_rate" in item for item in data["warnings"]),
                data["warnings"],
            )

    def test_adv2_huge_rate_in_cache_does_not_crash(self) -> None:
        """ADV-2: zehirli önbellek `--offline`da çökmez; yok sayılır."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            warm = run("--json", "--cache-ttl", "60", cwd=project, path=stub)
            self.assertEqual(warm.returncode, 0, warm.stderr)
            cache = project / ".orchestration" / "status-cache.json"
            envelope = json.loads(cache.read_text(encoding="utf-8"))
            envelope["data"]["epics"][0]["evaluations"]["discovery_rate"] = 10**400
            cache.write_text(json.dumps(envelope), encoding="utf-8")

            offline = run("--json", "--offline", cwd=project, path=stub)
            self.assertEqual(offline.returncode, 0, offline.stderr)
            data = payload(offline)
            self.assertEqual(data["epics"], [])
            self.assertTrue(data["stale"])
            self.assertTrue(
                any("önbellek geçersiz" in item for item in data["warnings"]),
                data["warnings"],
            )

    @unittest.skipIf(
        os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
        "izin testi POSIX kök olmayan kullanıcı ister",
    )
    def test_adv5_permission_error_message(self) -> None:
        """ADV-5: okunamayan dosya JSON değil, erişim hatası olarak raporlanır."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp, evaluations_doc({"12": self.RECORD})
            )
            path = project / ".kit" / "evaluations.json"
            path.chmod(0o000)
            try:
                proc = run("--json", cwd=project, path=stub)
            finally:
                path.chmod(0o644)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)
            self.assertTrue(
                any("erişilemedi" in item for item in data["warnings"]),
                data["warnings"],
            )
            self.assertFalse(
                any("JSON geçersiz" in item for item in data["warnings"]),
                data["warnings"],
            )

    def test_adv6_non_canonical_epic_keys_rejected(self) -> None:
        """ADV-6: 012/ 12 /+12/-5 anahtarları reddedilir, uyarı verir."""
        with tempfile.TemporaryDirectory() as tmp:
            keys = ("012", " 12 ", "+12", "-5", "12.0")
            project, stub = self.setup_project(
                tmp, evaluations_doc({key: self.RECORD for key in keys})
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertEqual(data["epics"][0]["evaluations"], NULL_EVALUATIONS)
            warnings = " ".join(data["warnings"])
            for key in keys:
                self.assertIn(f"epic anahtarı geçersiz: {key}", warnings)

    def test_adv7_non_calendar_date_rejected(self) -> None:
        """ADV-7: takvimde olmayan ISO (31 Şubat) ve geçerli artık gün."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp,
                evaluations_doc(
                    {
                        "12": {**self.RECORD, "updated_at": "2026-02-31T10:00:00Z"},
                    }
                ),
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            self.assertIsNone(data["epics"][0]["evaluations"]["updated_at"])
            self.assertTrue(
                any("updated_at" in item for item in data["warnings"]),
                data["warnings"],
            )

        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp,
                evaluations_doc(
                    {
                        "12": {**self.RECORD, "updated_at": "2024-02-29T10:00:00Z"},
                    }
                ),
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                payload(proc)["epics"][0]["evaluations"]["updated_at"],
                "2024-02-29T10:00:00Z",
            )

    def test_adv8_bounds_and_normalization(self) -> None:
        """ADV-8: sayı sınırı, pass<=total, boş batch, rate float normalizesi."""
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp,
                evaluations_doc(
                    {
                        "12": {
                            **self.RECORD,
                            "batch": "",
                            "cases_pass": 99,
                            "cases_total": 14,
                        }
                    }
                ),
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            block = data["epics"][0]["evaluations"]
            self.assertIsNone(block["batch"])
            self.assertIsNone(block["cases_pass"])
            self.assertIsNone(block["cases_total"])
            warnings = " ".join(data["warnings"])
            self.assertIn("batch geçersiz", warnings)
            self.assertIn("cases_pass > cases_total", warnings)

        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(
                tmp,
                evaluations_doc(
                    {
                        "12": {
                            **self.RECORD,
                            "cases_pass": 10**400,
                            "discovery_rate": 1,
                        }
                    }
                ),
            )
            proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            block = payload(proc)["epics"][0]["evaluations"]
            self.assertIsNone(block["cases_pass"])
            self.assertEqual(block["discovery_rate"], 1.0)
            self.assertIsInstance(block["discovery_rate"], float)


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
            self.assertEqual([cp["done"] for cp in epic["checkpoints"]], [True, True, False, False])
            # Her checkpoint kendi çocuğunu taşır: panel satırı `#13 · CP-1 ✓`.
            self.assertEqual([cp["leaf"] for cp in epic["checkpoints"]], [13, 13, 14, 14])

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
            self.assertEqual([cp["done"] for cp in epic["checkpoints"]], [False, False, False, False])


class DetailTests(unittest.TestCase):
    """CP-1: epic detayı için checkpoint listesi ve güncelleme zamanı."""

    def test_checkpoints_and_updated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            (project / "kit.config.yaml").write_text(
                'kit:\n  version: "0.0.0"\n'
                "tracker:\n  provider: github\n  repo: ali-demirPro/demir-kit-sdlc\n",
                encoding="utf-8",
            )
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(
                            12,
                            "Epic",
                            ("executing",),
                            EPIC_BODY,
                            updated_at="2026-11-04T09:00:00Z",
                        ),
                        issue(
                            13,
                            "Biten leaf",
                            ("leaf-done",),
                            LEAF_BODY,
                            updated_at="2026-11-04T10:00:00Z",
                        ),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            epic = payload(proc)["epics"][0]
            self.assertEqual(
                epic["checkpoints"],
                [
                    {"id": "CP-1", "title": "bir", "done": True, "leaf": 13},
                    {"id": "CP-2", "title": "iki", "done": True, "leaf": 13},
                ],
            )
            self.assertEqual(epic["updated_at"], "2026-11-04T09:00:00Z")
            self.assertEqual(
                epic["url"], "https://github.com/ali-demirPro/demir-kit-sdlc/issues/12"
            )

    def test_invalid_updated_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            proc = run(
                "--json",
                cwd=project,
                path=gh_fixture(
                    Path(tmp) / "bin",
                    [
                        issue(12, "Epic", ("executing",), EPIC_BODY),
                        issue(13, "Leaf", ("leaf-done",), LEAF_BODY),
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIsNone(payload(proc)["epics"][0]["updated_at"])

    def test_non_iso_updated_at_is_null(self) -> None:
        """ISO-8601 olmayan `updatedAt` panelde ham metin olarak çizilmez."""
        with tempfile.TemporaryDirectory() as tmp:
            project = project_dir(tmp)
            for broken in ("dün", "2026-11-04", "04.11.2026 09:00", "2026-13-99T99:99:99Z"):
                proc = run(
                    "--json",
                    cwd=project,
                    path=gh_fixture(
                        Path(tmp) / "bin",
                        [
                            issue(
                                12,
                                "Epic",
                                ("executing",),
                                EPIC_BODY,
                                updated_at=broken,
                            )
                        ],
                    ),
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIsNone(
                    payload(proc)["epics"][0]["updated_at"], f"{broken!r} null olmalı"
                )

    def test_offset_updated_at_is_kept(self) -> None:
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
                            ("executing",),
                            EPIC_BODY,
                            updated_at="2026-11-04T12:00:00+03:00",
                        )
                    ],
                ),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                payload(proc)["epics"][0]["updated_at"], "2026-11-04T12:00:00+03:00"
            )


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


def cycle_row(issue: int, stage: str, ts: str, reason: str = "", epic: int | None = None) -> dict:
    row = {"ts": ts, "issue": issue, "stage": stage, "actor": "test", "reason": reason}
    if epic is not None:
        row["epic"] = epic
    return row


def stamp(minutes_ago: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(
        timespec="seconds"
    )


class PulseTests(unittest.TestCase):
    """P10-2: pulse ve machinery `cycle.jsonl`dan türetilir; sıfır uydurulmaz."""

    def setup_project(self, tmp: str, rows: list[dict] | None) -> tuple[Path, Path]:
        project = Path(tmp) / "p"
        project.mkdir()
        (project / "kit.config.yaml").write_text(CONFIG, encoding="utf-8")
        if rows is not None:
            path = project / ".kit" / "cycle.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )
        stub = gh_fixture(
            Path(tmp) / "bin",
            [
                issue(12, "Epic", ("executing",), EPIC_BODY),
                issue(13, "Leaf bir", ("leaf-done",), LEAF_BODY),
                issue(14, "Leaf iki", ("executing",), LEAF_BODY),
            ],
        )
        return project, stub

    def test_pulse_counts_window(self) -> None:
        rows = [
            cycle_row(13, "agent-approved", stamp(90), epic=12),
            cycle_row(13, "gate", stamp(80), "CP-1 selected exit=0", 12),
            cycle_row(13, "gate", stamp(75), "CP-1 selected exit=1", 12),
            cycle_row(13, "gate", stamp(70), "CP-1 selected exit=0", 12),
            cycle_row(13, "review", stamp(65), epic=12),
            cycle_row(14, "blocked", stamp(50), epic=12),
            cycle_row(13, "leaf-done", stamp(60), epic=12),
            cycle_row(13, "leaf-done", stamp(30), epic=12),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp, rows)
            with unittest.mock.patch.dict(
                os.environ, {"DEMIR_KIT_CYCLE_ROOT": str(project)}
            ):
                proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            pulse = payload(proc)["pulse"]
            self.assertEqual(pulse["status"], "ok")
            self.assertEqual(pulse["window_days"], 7)
            self.assertEqual(pulse["leaves_done"], 2)
            self.assertEqual(pulse["gates"], 3)
            self.assertEqual(pulse["gate_failures"], 1)
            self.assertEqual(pulse["review_rounds"], 1)
            self.assertEqual(pulse["blocked"], 1)
            self.assertEqual(pulse["deferred"], 0)
            self.assertEqual(len(pulse["daily"]), 7)
            self.assertEqual(sum(pulse["daily"]), 2)
            self.assertEqual(pulse["lead"]["n"], 1)
            self.assertEqual(pulse["lead"]["p50"], 30.0)
            self.assertIsNone(pulse["prev_delta"])

    def test_missing_ledger_is_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp, None)
            with unittest.mock.patch.dict(
                os.environ, {"DEMIR_KIT_CYCLE_ROOT": str(project)}
            ):
                proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = payload(proc)
            pulse = data["pulse"]
            self.assertEqual(pulse["status"], "missing")
            for key in (
                "leaves_done",
                "prev_delta",
                "gates",
                "gate_failures",
                "review_rounds",
                "blocked",
                "deferred",
            ):
                self.assertIsNone(pulse[key], key)
            self.assertEqual(pulse["daily"], [])
            self.assertEqual(pulse["lead"], {"n": 0, "p50": None, "p90": None, "samples": []})
            self.assertIsNone(data["epics"][0]["machinery"])

    def test_machinery_scopes_to_epic(self) -> None:
        rows = [
            cycle_row(13, "gate", stamp(80), "CP-1 exit=0", 12),
            cycle_row(13, "gate", stamp(75), "CP-2 exit=1", 12),
            cycle_row(14, "leaf-done", stamp(40), epic=12),
            cycle_row(99, "gate", stamp(30), "CP-1 exit=1", 999),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp, rows)
            with unittest.mock.patch.dict(
                os.environ, {"DEMIR_KIT_CYCLE_ROOT": str(project)}
            ):
                proc = run("--json", cwd=project, path=stub)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            machinery = payload(proc)["epics"][0]["machinery"]
            self.assertEqual(machinery["gate_runs"], 2)
            self.assertEqual(machinery["gate_failures"], 1)
            self.assertEqual(machinery["leaves_done"], 1)
            self.assertEqual(machinery["prevented"], 0)

    def test_legacy_cache_without_pulse_is_accepted(self) -> None:
        rows = [cycle_row(13, "leaf-done", stamp(10), epic=12)]
        with tempfile.TemporaryDirectory() as tmp:
            project, stub = self.setup_project(tmp, rows)
            with unittest.mock.patch.dict(
                os.environ, {"DEMIR_KIT_CYCLE_ROOT": str(project)}
            ):
                first = run("--json", "--cache-ttl", "600", cwd=project, path=stub)
                self.assertEqual(first.returncode, 0, first.stderr)
                cache = project / ".orchestration" / "status-cache.json"
                envelope = json.loads(cache.read_text(encoding="utf-8"))
                envelope["data"].pop("pulse", None)
                for epic in envelope["data"]["epics"]:
                    epic.pop("machinery", None)
                cache.write_text(json.dumps(envelope), encoding="utf-8")

                second = run("--json", "--offline", cwd=project, path=stub)
            self.assertEqual(second.returncode, 0, second.stderr)
            data = payload(second)
            self.assertEqual(data["source"], "cache")
            self.assertEqual(data["pulse"]["status"], "missing")
            self.assertIsNone(data["epics"][0]["machinery"])


if __name__ == "__main__":
    unittest.main()
