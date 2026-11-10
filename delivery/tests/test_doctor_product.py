"""doctor --product offline digest layer (KIT-MANIFEST.json)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
DOCTOR = SCRIPTS / "doctor.py"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "vendor_sync_for_doctor", SCRIPTS / "vendor_sync.py"
)
vendor_sync = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(vendor_sync)

GIT = ["git", "-c", "user.email=test@example.com", "-c", "user.name=test"]


def make_product(base: Path) -> Path:
    root = base / "product"
    (root / "src").mkdir(parents=True)
    (root / "kit.config.yaml").write_text(
        'kit:\n  root: demir-kit\n  version: "2.64.0"\n  protocol: "2"\n',
        encoding="utf-8",
    )
    (root / "ecosystem.yaml").write_text(
        "products:\n  app:\n    surfaces:\n      web:\n        path: src\n"
        "        gates:\n          behavior: \"true\"\n",
        encoding="utf-8",
    )
    kit = root / "demir-kit"
    (kit / "delivery" / "scripts").mkdir(parents=True)
    (kit / "delivery" / "scripts" / "doctor.py").write_text("# vendored\n", encoding="utf-8")
    (kit / "VERSION").write_text("2.64.0\n", encoding="utf-8")
    (kit / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    vendor_sync.seal(kit)
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        [*GIT, "commit", "-qm", "fixture"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    return root


def init_kit_git(kit: Path) -> None:
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        [*GIT, "commit", "-qm", "kit"],
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
    ):
        subprocess.run(command, cwd=kit, check=True, capture_output=True)


def doctor(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DOCTOR), "--product", "--root", str(root), *extra],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


class DoctorProductManifestTests(unittest.TestCase):
    def test_reports_commit_and_digest_layers_separately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_product(Path(directory))
            result = doctor(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("kit pin: commit not_run", result.stdout)
            self.assertIn("kit pin: manifest digest ok", result.stdout)

    def test_commit_ok_line_is_reported_next_to_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_product(Path(directory))
            init_kit_git(root / "demir-kit")
            result = doctor(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("kit pin: commit ok", result.stdout)
            self.assertIn("kit pin: manifest digest ok", result.stdout)

    def test_tampered_file_reports_name_expected_and_actual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_product(Path(directory))
            target = root / "demir-kit" / "delivery" / "scripts" / "doctor.py"
            expected = vendor_sync.digest(target)
            target.write_text("# tampered\n", encoding="utf-8")
            actual = vendor_sync.digest(target)
            self.assertNotEqual(expected, actual)

            result = doctor(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("kit pin: manifest digest fail", result.stdout)
            self.assertIn("değişmiş dosya delivery/scripts/doctor.py", result.stdout)
            self.assertIn(expected, result.stdout)
            self.assertIn(actual, result.stdout)
            # Commit layer is reported independently; digest failure does not
            # rewrite the ancestry line.
            self.assertIn("kit pin: commit not_run", result.stdout)

    def test_missing_and_extra_files_are_named(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_product(Path(directory))
            kit = root / "demir-kit"
            (kit / "install.sh").unlink()
            (kit / "delivery" / "extra.md").write_text("extra\n", encoding="utf-8")

            result = doctor(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("eksik dosya install.sh", result.stdout)
            self.assertIn("fazladan dosya delivery/extra.md", result.stdout)

    def test_missing_manifest_is_not_run_not_green(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_product(Path(directory))
            (root / "demir-kit" / vendor_sync.MANIFEST_NAME).unlink()

            plain = doctor(root)
            self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
            self.assertIn("kit pin: manifest digest not_run", plain.stdout)
            self.assertIn("KIT-MANIFEST.json yok", plain.stdout)

            strict = doctor(root, "--strict")
            self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)

    def test_doctor_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = make_product(Path(directory))
            before = {
                path: vendor_sync.digest(path)
                for path in (root / "demir-kit").rglob("*")
                if path.is_file()
            }
            doctor(root)
            after = {
                path: vendor_sync.digest(path)
                for path in (root / "demir-kit").rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
