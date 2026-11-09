"""Tests for the sandboxed session runner and its normalized evidence."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("eval_run", SCRIPTS / "eval_run.py")
eval_run = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(eval_run)

FIXED_TIME = "2026-11-09T10:00:00+00:00"


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


def make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    assert git(root, "init", "--quiet").returncode == 0
    (root / "app.txt").write_text("one\n", encoding="utf-8")
    assert git(root, "add", "-A").returncode == 0
    assert (
        git(
            root,
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=test",
            "commit",
            "--quiet",
            "-m",
            "baseline",
        ).returncode
        == 0
    )
    return root


def base_spec(**overrides) -> dict:
    record = {
        "case": "T-1",
        "command": [sys.executable, "-c", "print('hello')"],
        "sandbox": "none",
        "inputs": ["merhaba"],
        "timeout": 30,
        "created_at": FIXED_TIME,
    }
    record.update(overrides)
    return record


class SessionFileContractTests(unittest.TestCase):
    def test_session_directory_and_five_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_dir = Path(directory) / "session"
            result = eval_run.run_session(base_spec(case="T-1"), out_dir=session_dir)

            for relative in eval_run.EVIDENCE_FILES:
                self.assertTrue(
                    (session_dir / relative).is_file(), f"eksik dosya: {relative}"
                )

            written_spec = json.loads(
                (session_dir / "spec.json").read_text(encoding="utf-8")
            )
            self.assertEqual(written_spec["case"], "T-1")
            self.assertEqual(written_spec["demir_kit_version"], "2")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["state"], "terminal")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["attempt"], 1)

            inputs = eval_run.read_ndjson(session_dir / "session" / "inputs.ndjson")
            self.assertEqual(inputs[0]["text"], "merhaba")

            events = eval_run.read_ndjson(session_dir / "session" / "events.ndjson")
            self.assertGreater(len(events), 0)
            texts = [
                event["payload"].get("text")
                for event in events
                if event["payload"].get("type") == "stdout"
            ]
            self.assertIn("hello", texts)

    def test_session_directory_must_stay_outside_repo(self) -> None:
        with self.assertRaises(eval_run.SessionError):
            eval_run.run_session(base_spec(), out_dir=ROOT / ".eval-run-tmp")

    def test_clone_sandbox_writes_diff_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = make_repo(Path(directory) / "source")
            session_dir = Path(directory) / "session"
            command = [
                sys.executable,
                "-c",
                "open('new.txt','w').write('x')\nopen('app.txt','a').write('two\\n')",
            ]
            result = eval_run.run_session(
                base_spec(command=command, sandbox="clone", source=str(source)),
                out_dir=session_dir,
            )
            self.assertEqual(result["status"], "pass")
            patch = (session_dir / "session" / "diff.patch").read_text(
                encoding="utf-8"
            )
            self.assertIn("new.txt", patch)
            self.assertIn("app.txt", patch)


class RuntimeDependencyTests(unittest.TestCase):
    def test_runner_never_calls_node_docker_or_npm(self) -> None:
        source = (SCRIPTS / "eval_run.py").read_text(encoding="utf-8")
        self.assertEqual(
            re.findall(r"\b(node|docker|npm|npx|yarn|pnpm)\b", source, re.I), []
        )
        self.assertNotIn("shell=True", source)

    def test_runner_uses_python3_and_git_only(self) -> None:
        source = (SCRIPTS / "eval_run.py").read_text(encoding="utf-8")
        self.assertIn("git", source)
        with tempfile.TemporaryDirectory() as directory:
            result = eval_run.run_session(
                base_spec(), out_dir=Path(directory) / "session"
            )
            self.assertEqual(result["status"], "pass")


class NormalizationTests(unittest.TestCase):
    def test_same_input_produces_identical_ndjson(self) -> None:
        raw = [
            {"seq": 3, "turn": 1, "payload": {"type": "prompt", "text": "a"}},
            {"turn": 1, "payload": {"type": "tool", "text": "b"}},
            {"seq": 8, "turn": 2, "payload": {"type": "prompt", "text": "c"}},
        ]
        first = eval_run.normalize_events(raw, FIXED_TIME)
        second = eval_run.normalize_events(raw, FIXED_TIME)
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = eval_run.write_ndjson(root / "one.ndjson", first)
            two = eval_run.write_ndjson(root / "two.ndjson", second)
            self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_seq_comes_from_source_not_list_index(self) -> None:
        raw = [
            {"seq": 4, "payload": {"type": "a"}},
            {"payload": {"type": "b"}},
            {"id": "9", "payload": {"type": "c"}},
            {"payload": {"type": "d"}},
        ]
        events = eval_run.normalize_events(raw, FIXED_TIME)
        self.assertEqual([event["seq"] for event in events], [4, 5, 9, 10])
        for index, event in enumerate(events):
            self.assertNotEqual(event["seq"], index)

    def test_filtering_preserves_gaps(self) -> None:
        raw = [
            {"payload": {"type": "keep"}},
            {"payload": {"type": "drop"}},
            {"payload": {"type": "keep"}},
            {"payload": {"type": "drop"}},
            {"payload": {"type": "keep"}},
        ]
        events = eval_run.normalize_events(raw, FIXED_TIME)
        kept = eval_run.filter_events(
            events, lambda event: event["payload"]["type"] == "keep"
        )
        self.assertEqual([event["seq"] for event in kept], [0, 2, 4])
        self.assertEqual([event["seq"] for event in events], [0, 1, 2, 3, 4])

    def test_every_event_carries_the_four_fields(self) -> None:
        events = eval_run.normalize_events(
            [{"turn": 2, "payload": {"type": "x"}}], FIXED_TIME
        )
        self.assertEqual(set(events[0]), {"seq", "turn", "observedAt", "payload"})
        self.assertEqual(events[0]["turn"], 2)
        self.assertTrue(events[0]["observedAt"].startswith("2026-11-09T10:00:00"))


class EvidenceReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.directory.name) / "session"
        self.result = eval_run.run_session(
            base_spec(command=[sys.executable, "-c", "print('trace')"]),
            out_dir=self.session_dir,
        )
        self.events = eval_run.read_ndjson(
            self.session_dir / "session" / "events.ndjson"
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_trace_reference_is_accepted(self) -> None:
        errors = eval_run.validate_evidence(
            {"kind": "trace", "seq": 1}, self.events, self.session_dir, 1
        )
        self.assertEqual(errors, [])

    def test_artifact_reference_is_accepted(self) -> None:
        errors = eval_run.validate_evidence(
            {
                "kind": "artifact",
                "artifact": "session/events.ndjson",
                "line": 1,
            },
            self.events,
            self.session_dir,
            1,
        )
        self.assertEqual(errors, [])

    def test_trace_must_exist(self) -> None:
        errors = eval_run.validate_evidence(
            {"kind": "trace", "seq": 999}, self.events, self.session_dir, 1
        )
        self.assertTrue(errors)

    def test_artifact_attempt_outside_limit_is_rejected(self) -> None:
        errors = eval_run.validate_evidence(
            {
                "kind": "artifact",
                "artifact": "session/events.ndjson",
                "attempt": 2,
                "line": 1,
            },
            self.events,
            self.session_dir,
            1,
        )
        self.assertTrue(any("deneme sınırı" in message for message in errors))

    def test_artifact_line_outside_file_is_rejected(self) -> None:
        errors = eval_run.validate_evidence(
            {
                "kind": "artifact",
                "artifact": "session/events.ndjson",
                "line": 9999,
            },
            self.events,
            self.session_dir,
            1,
        )
        self.assertTrue(any("dosya dışında" in message for message in errors))

    def test_artifact_path_cannot_escape_session(self) -> None:
        for artifact in ("../secret", "/etc/passwd", "session/../../x"):
            errors = eval_run.validate_evidence(
                {"kind": "artifact", "artifact": artifact, "line": 1},
                self.events,
                self.session_dir,
                1,
            )
            self.assertTrue(errors, artifact)

    def test_empty_reference_is_rejected(self) -> None:
        self.assertTrue(
            eval_run.validate_evidence({}, self.events, self.session_dir, 1)
        )
        self.assertTrue(
            eval_run.validate_references(
                [{"kind": "trace", "seq": 999}, {}],
                self.events,
                self.session_dir,
                1,
            )
        )

    def test_second_attempt_archives_first_attempt(self) -> None:
        reread = eval_run.run_session(
            base_spec(
                command=[sys.executable, "-c", "print('second')"], attempts=2
            ),
            out_dir=self.session_dir,
        )
        self.assertEqual(reread["attempt"], 2)
        self.assertEqual(reread["attempts"], 2)
        for attempt in (1, 2):
            errors = eval_run.validate_evidence(
                {
                    "kind": "artifact",
                    "artifact": "session/events.ndjson",
                    "attempt": attempt,
                    "line": 1,
                },
                self.events,
                self.session_dir,
                2,
            )
            self.assertEqual(errors, [], f"attempt {attempt}")


class StateMachineTests(unittest.TestCase):
    def test_happy_path_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            machine = eval_run.SessionStateMachine(Path(directory))
            self.assertEqual(machine.state, "preparing")
            machine.transition("running")
            machine.transition("waiting", "girdi bekleniyor")
            machine.transition("running", "girdi geldi")
            machine.transition("terminal")
            self.assertEqual(machine.state, "terminal")
            snapshot = json.loads(
                (Path(directory) / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [entry["to"] for entry in snapshot["history"]],
                ["preparing", "running", "waiting", "running", "terminal"],
            )

    def test_invalid_transition_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            machine = eval_run.SessionStateMachine(Path(directory))
            with self.assertRaises(eval_run.StateError):
                machine.transition("waiting")
            machine.transition("blocked")
            with self.assertRaises(eval_run.StateError):
                machine.transition("waiting")


class UnexpectedDeathTests(unittest.TestCase):
    def test_unexpected_death_preserves_evidence_and_reports_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_dir = Path(directory) / "session"
            command = [
                sys.executable,
                "-c",
                "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
            ]
            result = eval_run.run_session(
                base_spec(command=command, timeout=30), out_dir=session_dir
            )

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["state"], "blocked")
            self.assertTrue(result["unexpected_death"])
            self.assertIsNotNone(result["recovery"])
            self.assertTrue(result["recovery"]["evidence_intact"])
            self.assertIn("resume_command", result["recovery"])

            for relative in eval_run.EVIDENCE_FILES:
                self.assertTrue(
                    (session_dir / relative).is_file(), f"eksik kanıt: {relative}"
                )
            self.assertTrue(
                (session_dir / "session" / "events.ndjson").stat().st_size > 0
            )
            state = json.loads(
                (session_dir / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["state"], "blocked")
            self.assertIn("blocked", [entry["to"] for entry in state["history"]])


class SpecValidationTests(unittest.TestCase):
    def test_shell_string_command_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(eval_run.SessionError):
                eval_run.run_session(
                    base_spec(command="echo hi"), out_dir=Path(directory) / "s"
                )

    def test_attempt_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_dir = Path(directory) / "session"
            spec = base_spec(attempts=1)
            eval_run.run_session(spec, out_dir=session_dir)
            with self.assertRaises(eval_run.SessionError):
                eval_run.run_session(spec, out_dir=session_dir)


if __name__ == "__main__":
    unittest.main()
