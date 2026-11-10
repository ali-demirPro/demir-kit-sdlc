"""Tests for the read-only health-check tool table."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
PROTOCOL = ROOT / "delivery" / "protocol" / "health-check.md"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "health_check", SCRIPTS / "health_check.py"
)
health_check = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(health_check)


def bin_dir(root: Path, tools: list[str]) -> Path:
    path = root / "bin"
    path.mkdir()
    for name in tools:
        executable = path / name
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    return path


class HealthTableTests(unittest.TestCase):
    def test_table_has_sixteen_rows_with_known_tools(self) -> None:
        rows = health_check.load_table(PROTOCOL)
        self.assertEqual(len(rows), 16)
        self.assertEqual([row["id"] for row in rows], list(range(1, 17)))
        self.assertEqual(
            {row["id"] for row in rows if row["required"]},
            {1, 2, 3, 4, 5, 6, 7, 11},
        )
        self.assertTrue(all(row["tool"] in health_check.TOOLS for row in rows))
        self.assertEqual(
            [row["check"] for row in rows][0], "ecosystem.yaml ve yüzey yolları"
        )
        self.assertEqual(
            [row["check"] for row in rows][-1], "monetization-brief.md"
        )

    def test_missing_required_tool_is_not_run_and_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = bin_dir(Path(directory), ["python3", "bash", "git", "gh"])
            data = health_check.run(PROTOCOL, str(path))
            self.assertFalse(data["ready"])
            self.assertTrue(any(item.startswith("7.") for item in data["blockers"]))
            self.assertEqual(data["rows"][6]["status"], "not_run")
            self.assertEqual(data["rows"][6]["reason"], "araç PATH'te yok: orca")
            self.assertTrue(data["question"])
            self.assertEqual(data["question"].count("?"), 1)
            self.assertIn("şimdi mi", data["question"])
            self.assertIn("sonraki tura mı", data["question"])
            self.assertNotIn("PATH", data["question"])
            self.assertNotIn("health-check", data["question"])
            # Optional orca rows are not blockers, but they are not passes.
            self.assertEqual(data["rows"][7]["status"], "not_run")
            self.assertEqual(data["rows"][8]["status"], "not_run")
            self.assertTrue(any(item.startswith("8.") for item in data["warnings"]))

    def test_all_tools_present_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = bin_dir(Path(directory), list(health_check.TOOLS))
            data = health_check.run(PROTOCOL, str(path))
            self.assertTrue(data["ready"])
            self.assertEqual(data["blockers"], [])
            self.assertEqual(data["warnings"], [])
            self.assertIsNone(data["question"])
            self.assertTrue(all(row["status"] == "pass" for row in data["rows"]))

    def test_unknown_tool_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.md"
            text = PROTOCOL.read_text(encoding="utf-8").replace(
                "| 16 | monetization-brief.md | python3 | false |",
                "| 16 | monetization-brief.md | toolbox | false |",
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                health_check.load_table(path)
            self.assertIn("bilinmeyen araç", str(ctx.exception))

    def test_unknown_control_name_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.md"
            text = PROTOCOL.read_text(encoding="utf-8").replace(
                "| 5 | native selftest | python3 | true |",
                "| 5 | bilinmeyen kontrol | python3 | true |",
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                health_check.load_table(path)
            self.assertIn("bilinmeyen kontrol", str(ctx.exception))

    def test_duplicate_control_name_breaks_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.md"
            text = PROTOCOL.read_text(encoding="utf-8").replace(
                "| 6 | gh auth status | gh | true |",
                "| 6 | native selftest | gh | true |",
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                health_check.load_table(path)
            self.assertIn("beklenen: gh auth status", str(ctx.exception))

    def test_duplicate_control_id_breaks_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.md"
            text = PROTOCOL.read_text(encoding="utf-8").replace(
                "| 16 | monetization-brief.md | python3 | false |",
                "| 15 | monetization-brief.md | python3 | false |",
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                health_check.load_table(path)
            self.assertIn("1..16", str(ctx.exception))

    def test_missing_row_breaks_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.md"
            text = PROTOCOL.read_text(encoding="utf-8")
            text = text.replace(
                "| 16 | monetization-brief.md | python3 | false |\n", ""
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                health_check.load_table(path)
            self.assertIn("16 satır", str(ctx.exception))

    def test_run_is_read_only_and_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = bin_dir(Path(directory), list(health_check.TOOLS))
            real_open = Path.open

            def read_only(file_path, mode="r", *args, **kwargs):
                if any(flag in mode for flag in "wax+"):
                    raise AssertionError("dosya yazılmaz")
                return real_open(file_path, mode, *args, **kwargs)

            with patch("socket.socket", side_effect=AssertionError("ağ yok")), patch.object(
                Path, "open", read_only
            ):
                data = health_check.run(PROTOCOL, str(path))
            self.assertTrue(data["ready"])

    def test_json_output_carries_the_same_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = bin_dir(Path(directory), list(health_check.TOOLS))
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "health_check.py"),
                    "--json",
                    "--path",
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            expected = health_check.run(PROTOCOL, str(path))
            self.assertEqual(data, expected)
            self.assertTrue(data["ready"])
            self.assertEqual(len(data["rows"]), 16)
            self.assertTrue(
                {"check", "tool", "status", "reason"} <= set(data["rows"][0])
            )


if __name__ == "__main__":
    unittest.main()
