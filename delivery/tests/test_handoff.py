"""Tests for the epic handoff helper."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("handoff", SCRIPTS / "handoff.py")
handoff = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(handoff)


class HandoffTests(unittest.TestCase):
    def test_note_carries_the_contract_fields(self) -> None:
        note = handoff.handoff_note(277, "282", "N5 bitti", "N7")
        for text in ("#277", "282", "N5 bitti", "Sıradaki: N7"):
            self.assertIn(text, note)

    def test_launch_uses_orca_agent_launch(self) -> None:
        command = handoff.launch_command(ROOT, "devam")
        self.assertEqual(command[:3], ["orca", "agent", "launch"])
        self.assertIn(f"path:{ROOT}", command)
        self.assertIn("opencode2", command)
        self.assertIn("--prompt", command)

    def test_close_uses_terminal_close(self) -> None:
        self.assertEqual(
            handoff.close_command("term_1")[:4],
            ["orca", "terminal", "close", "--terminal"],
        )

    def test_dry_run_does_not_shell_out(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with patch.object(handoff.subprocess, "run") as run, redirect_stdout(buffer):
            argv = [
                "handoff.py",
                "--issue",
                "277",
                "--close-terminal",
                "term_x",
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(handoff.main(), 0)
        run.assert_not_called()
        output = buffer.getvalue()
        self.assertIn("orca agent launch", output)
        self.assertIn("orca terminal close", output)

    def test_retry_launch_is_forwarded(self) -> None:
        command = handoff.launch_command(ROOT, "devam", "op_1")
        self.assertEqual(command[-2:], ["--retry-launch", "op_1"])

    def test_apply_posts_launches_and_closes(self) -> None:
        result = type("R", (), {"returncode": 0, "stderr": ""})()
        with patch.object(handoff, "post", return_value=True) as post, patch.object(
            handoff.subprocess, "run", return_value=result
        ) as run, patch.object(handoff, "close_terminal", return_value=True) as close, patch.object(
            sys, "argv",
            ["handoff.py", "--issue", "277", "--apply", "--close-terminal", "t1"],
        ):
            self.assertEqual(handoff.main(), 0)
        post.assert_called_once()
        self.assertEqual(run.call_args.args[0][:3], ["orca", "agent", "launch"])
        close.assert_called_once_with("t1")

    def test_apply_stops_when_launch_fails(self) -> None:
        failed = type("R", (), {"returncode": 1, "stderr": "no"})()
        with patch.object(handoff, "post", return_value=True), patch.object(
            handoff.subprocess, "run", return_value=failed
        ), patch.object(handoff, "close_terminal") as close, patch.object(
            sys, "argv", ["handoff.py", "--issue", "277", "--apply"]
        ):
            with self.assertRaises(SystemExit):
                handoff.main()
        close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
