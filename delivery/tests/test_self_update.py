"""Tests for one-command kit self update."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("self_update", SCRIPTS / "self_update.py")
self_update = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(self_update)

UPSTREAM = "https://github.com/ali-demirPro/demir-kit-sdlc.git"
OTHER = "https://github.com/example/other.git"


def git_init(root: Path, origin: str | None = None) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    if origin:
        subprocess.run(["git", "remote", "add", "origin", origin], cwd=root, check=True)


def write_config(root: Path, body: str) -> None:
    (root / "kit.config.yaml").write_text(body)


def make_vendored(root: Path, upstream: str | None = UPSTREAM) -> None:
    upstream_block = f"  upstream:\n    git: {upstream}\n" if upstream else ""
    write_config(
        root,
        "kit:\n"
        "  root: demir-kit\n"
        '  version: "2.56.0"\n'
        '  protocol: "2"\n' + upstream_block,
    )
    kit = root / "demir-kit"
    (kit / "delivery" / "scripts").mkdir(parents=True)
    (kit / "delivery" / "scripts" / "doctor.sh").write_text("#!/bin/sh\n")
    (kit / "delivery" / "scripts" / "vendor_sync.py").write_text("")
    (kit / "VERSION").write_text("2.56.0\n")
    (root / "install.sh").write_text("#!/bin/sh\n")


def make_self(root: Path, upstream: str = UPSTREAM, origin: str | None = None) -> None:
    write_config(
        root,
        'kit:\n  root: "."\n  version: "2.57.0"\n  protocol: "2"\n'
        f"  upstream:\n    git: {upstream}\n",
    )
    (root / "VERSION").write_text("2.57.0\n")
    (root / "delivery" / "scripts").mkdir(parents=True)
    (root / "delivery" / "scripts" / "doctor.sh").write_text("#!/bin/sh\n")
    git_init(root, origin or upstream)


def make_submodule(root: Path, version: str = "2.58.0") -> Path:
    """Ürün içinde git submodule olarak duran kit (`.git` dosyası)."""
    write_config(
        root,
        "kit:\n"
        "  root: demir-kit\n"
        '  version: "2.57.0"\n'
        '  protocol: "2"\n'
        f"  upstream:\n    git: {UPSTREAM}\n",
    )
    kit = root / "demir-kit"
    (kit / "delivery" / "scripts").mkdir(parents=True)
    (kit / ".git").write_text("gitdir: ../.git/modules/demir-kit\n")
    (kit / "VERSION").write_text(f"{version}\n")
    (kit / "delivery" / "scripts" / "doctor.sh").write_text("#!/bin/sh\n")
    return kit


def make_uninitialized_submodule(root: Path, path: str = "demir-kit") -> None:
    """Henüz `submodule update --init` çalışmamış kit: yalnız `.gitmodules`."""
    write_config(
        root,
        "kit:\n"
        "  root: demir-kit\n"
        '  version: "2.57.0"\n'
        '  protocol: "2"\n'
        f"  upstream:\n    git: {UPSTREAM}\n",
    )
    (root / ".gitmodules").write_text(
        '[submodule "demir-kit"]\n'
        f"\tpath = {path}\n"
        f"\turl = {UPSTREAM}\n"
    )


class PlanTests(unittest.TestCase):
    def test_plan_vendored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_vendored(root)
            plan = self_update.build_plan(root, cache_dir=Path(directory) / "cache")
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["mode"], "vendored")
            self.assertEqual(plan["project"], str(root.resolve()))
            self.assertEqual(plan["kit_root"], str((root / "demir-kit").resolve()))
            self.assertEqual(plan["version"], "2.56.0")
            self.assertEqual(plan["upstream"], UPSTREAM)
            self.assertEqual(
                [item["name"] for item in plan["steps"]],
                ["clone", "vendor_sync", "skills", "doctor"],
            )
            clone = plan["steps"][0]["command"]
            # `--` upstream'den (URL) hemen önce: değer seçenek gibi okunmaz.
            self.assertEqual(
                clone,
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    "main",
                    "--",
                    UPSTREAM,
                    str((Path(directory) / "cache").resolve()),
                ],
            )
            self.assertEqual(
                plan["steps"][-1]["command"][-3:],
                ["--product", "--root", str(root.resolve())],
            )

    def test_self_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            root.mkdir()
            make_self(root)
            plan = self_update.build_plan(root)
            self.assertEqual(plan["mode"], "self")
            self.assertEqual(plan["kit_root"], str(root.resolve()))
            self.assertEqual(plan["version"], "2.57.0")
            self.assertEqual([item["name"] for item in plan["steps"]], ["pull", "doctor"])
            self.assertEqual(
                plan["steps"][0]["command"],
                ["git", "-C", str(root.resolve()), "pull", "--ff-only"],
            )
            self.assertEqual(
                plan["steps"][1]["command"],
                [str(root.resolve() / "delivery" / "scripts" / "doctor.sh")],
            )

    def test_self_requires_matching_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            source = Path(directory) / "source"
            root.mkdir()
            source.mkdir()
            make_self(root, origin=OTHER)
            (source / "delivery" / "scripts").mkdir(parents=True)
            (source / "delivery" / "scripts" / "vendor_sync.py").write_text("")
            (source / "install.sh").write_text("#!/bin/sh\n")
            (source / "VERSION").write_text("2.57.0\n")
            plan = self_update.build_plan(
                root,
                source=source,
                skip_skills=True,
                cache_dir=Path(directory) / "cache",
            )
            self.assertEqual(plan["mode"], "vendored")
            self.assertIn("vendor_sync", [item["name"] for item in plan["steps"]])

    def test_submodule_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            kit = make_submodule(root)
            # Submodule `.git` bir dosyadır (gitlink), dizin değil.
            self.assertTrue((kit / ".git").is_file())
            plan = self_update.build_plan(root)
            self.assertEqual(plan["mode"], "submodule")
            self.assertEqual(plan["kit_root"], str(kit.resolve()))
            # `.git` dizini biçimi de submodule sayılır.
            (kit / ".git").unlink()
            (kit / ".git").mkdir()
            self.assertEqual(self_update.build_plan(root)["mode"], "submodule")

    def test_uninitialized_submodule_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_uninitialized_submodule(root)
            # Kit dizini hiç yok: `.git` de yok, mod yine `submodule` olmalı.
            self.assertFalse((root / "demir-kit").exists())
            plan = self_update.build_plan(root)
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["mode"], "submodule")
            self.assertEqual(plan["kit_root"], str((root / "demir-kit").resolve()))
            self.assertEqual(
                [item["name"] for item in plan["steps"]],
                ["submodule", "config", "doctor"],
            )
            self.assertEqual(
                plan["steps"][0]["command"],
                [
                    "git",
                    "-C",
                    str(root.resolve()),
                    "submodule",
                    "update",
                    "--init",
                    "--remote",
                    "--",
                    "demir-kit",
                ],
            )
            # Ref verilince `--remote` yok: init + fetch/checkout.
            pinned = self_update.build_plan(root, ref="v2.58.0")
            self.assertNotIn("--remote", pinned["steps"][0]["command"])
            self.assertEqual(
                [item["name"] for item in pinned["steps"]],
                ["submodule", "fetch", "checkout", "config", "doctor"],
            )

    def test_submodule_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            kit = make_submodule(root)
            plan = self_update.build_plan(root)
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["version"], "2.58.0")
            self.assertEqual(
                [item["name"] for item in plan["steps"]],
                ["submodule", "config", "doctor"],
            )
            self.assertEqual(
                plan["steps"][0]["command"],
                [
                    "git",
                    "-C",
                    str(root.resolve()),
                    "submodule",
                    "update",
                    "--init",
                    "--remote",
                    "--",
                    "demir-kit",
                ],
            )
            self.assertEqual(plan["steps"][1], {"name": "config", "internal": "config"})
            self.assertEqual(
                plan["steps"][2]["command"],
                [
                    str(kit.resolve() / "delivery" / "scripts" / "doctor.sh"),
                    "--product",
                    "--root",
                    str(root.resolve()),
                ],
            )

            pinned = self_update.build_plan(root, ref="v2.58.0")
            self.assertEqual(
                [item["name"] for item in pinned["steps"]],
                ["submodule", "fetch", "checkout", "config", "doctor"],
            )
            # `--ref` varken `--remote` yok: tek ağ turu init, sonra pinleme.
            self.assertEqual(
                pinned["steps"][0]["command"],
                [
                    "git",
                    "-C",
                    str(root.resolve()),
                    "submodule",
                    "update",
                    "--init",
                    "--",
                    "demir-kit",
                ],
            )
            self.assertEqual(
                pinned["steps"][1]["command"],
                [
                    "git",
                    "-C",
                    str(kit.resolve()),
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    "--",
                    "v2.58.0",
                ],
            )
            self.assertEqual(
                pinned["steps"][2]["command"],
                ["git", "-C", str(kit.resolve()), "checkout", "--detach", "FETCH_HEAD"],
            )

    def test_submodule_config_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_submodule(root, version="2.58.0")
            plan = self_update.build_plan(root)
            config_step = [item for item in plan["steps"] if item["name"] == "config"]
            results = self_update.apply_plan({**plan, "steps": config_step})
            self.assertEqual(results, [{"name": "config", "exit_code": 0, "ok": True}])
            self.assertIn(
                '  version: "2.58.0"', (root / "kit.config.yaml").read_text()
            )

    def test_config_preserves_comments_and_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            original = (
                "# üst yorum\r\n"
                "kit:\r\n"
                "  root: demir-kit\r\n"
                "  # sürüm yorumu\r\n"
                '  version: "2.57.0"  # eski sürüm\r\n'
                '  protocol: "2"\r\n'
                "\r\n"
                "product:\r\n"
                '  name: "örnek"\r\n'
            )
            (root / "kit.config.yaml").write_bytes(original.encode("utf-8"))
            self_update.update_config(root, "2.58.0")
            text = (root / "kit.config.yaml").read_bytes().decode("utf-8")
            self.assertIn("# üst yorum\r\n", text)
            self.assertIn("  # sürüm yorumu\r\n", text)
            self.assertIn('  version: "2.58.0"  # eski sürüm\r\n', text)
            self.assertNotIn("2.57.0", text)
            self.assertEqual(text.count("\r\n"), original.count("\r\n"))
            self.assertNotIn("\n", text.replace("\r\n", ""))

    def test_config_adds_missing_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            (root / "kit.config.yaml").write_text(
                "# yorum\n"
                "kit:\n"
                "  root: demir-kit\n"
                '  protocol: "2"\n'
                "\n"
                "product:\n"
                '  name: "örnek"\n'
            )
            self_update.update_config(root, "2.58.0")
            text = (root / "kit.config.yaml").read_text()
            self.assertIn('  version: "2.58.0"\n', text)
            self.assertLess(text.index("version:"), text.index("product:"))
            self.assertIn("# yorum\n", text)

    def test_config_step_stops_on_missing_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            kit = make_submodule(root)
            (kit / "VERSION").unlink()
            plan = self_update.build_plan(root)
            config_step = [item for item in plan["steps"] if item["name"] == "config"]
            results = self_update.apply_plan({**plan, "steps": config_step})
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0]["ok"])
            self.assertIn("VERSION bulunamadı", results[0]["error"])

    def test_bad_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_submodule(root)
            values = (
                "",
                " ",
                "-x",
                "--upload-pack=/bin/sh",
                "a b",
                "a..b",
                "a:b",
                "a*b",
                "a^b",
                "a~1",
                "a@b",
                "@",
                "a\\b",
            )
            for value in values:
                with self.subTest(ref=value):
                    with self.assertRaises(ValueError) as caught:
                        self_update.build_plan(root, ref=value)
                    self.assertIn("--ref", str(caught.exception))

    def test_refspec_chars_rejected_message(self) -> None:
        for value in ("main:evil", "refs/*", "HEAD^", "v1~2", "@{upstream}", "a\\b"):
            with self.subTest(ref=value):
                with self.assertRaises(ValueError) as caught:
                    self_update.validate_ref(value)
                self.assertIn("refspec", str(caught.exception))

    def test_missing_upstream_is_plan_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_vendored(root, upstream=None)
            with self.assertRaises(ValueError) as caught:
                self_update.build_plan(root, cache_dir=Path(directory) / "cache")
            self.assertIn("kit.upstream.git yok", str(caught.exception))

    def test_dash_upstream_is_plan_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_vendored(root, upstream="--upload-pack=/bin/sh")
            with self.assertRaises(ValueError) as caught:
                self_update.build_plan(root, cache_dir=Path(directory) / "cache")
            message = str(caught.exception)
            self.assertIn("'-' ile başlayamaz", message)

    def test_unsupported_upstream_is_plan_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_vendored(root, upstream="github.com/example/kit")
            with self.assertRaises(ValueError) as caught:
                self_update.build_plan(root, cache_dir=Path(directory) / "cache")
            self.assertIn("desteklenmeyen biçim", str(caught.exception))

    def test_cache_that_is_not_a_repo_is_plan_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            cache = Path(directory) / "cache"
            root.mkdir()
            cache.mkdir()
            (cache / "not-a-repo.txt").write_text("x\n")
            make_vendored(root)
            with self.assertRaises(ValueError) as caught:
                self_update.build_plan(root, cache_dir=cache)
            message = str(caught.exception)
            self.assertIn("önbellek bir git deposu değil", message)
            self.assertIn(str(cache.resolve()), message)

    def test_cache_repo_fetches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            cache = Path(directory) / "cache"
            root.mkdir()
            cache.mkdir()
            git_init(cache, UPSTREAM)
            make_vendored(root)
            plan = self_update.build_plan(root, cache_dir=cache)
            self.assertEqual(
                [item["name"] for item in plan["steps"]][:2], ["fetch", "reset"]
            )
            self.assertEqual(
                plan["steps"][0]["command"],
                ["git", "-C", str(cache.resolve()), "fetch", "--depth", "1", "origin", "main"],
            )

    def test_apply_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            source = Path(directory) / "source"
            root.mkdir()
            source.mkdir()
            make_vendored(root)
            (source / "delivery" / "scripts").mkdir(parents=True)
            (source / "delivery" / "scripts" / "vendor_sync.py").write_text("")
            (source / "install.sh").write_text("#!/bin/sh\n")
            (source / "VERSION").write_text("2.57.0\n")
            plan = self_update.build_plan(
                root,
                source=source,
                skip_skills=True,
                cache_dir=Path(directory) / "cache",
            )
            self.assertEqual(plan["version"], "2.57.0")
            self.assertEqual(
                [item["name"] for item in plan["steps"]], ["vendor_sync", "doctor"]
            )
            command = plan["steps"][0]["command"]
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(
                command[1], str((source / "delivery" / "scripts" / "vendor_sync.py").resolve())
            )
            self.assertEqual(
                command[-5:],
                [
                    "--source",
                    str(source.resolve()),
                    "--target",
                    str(root.resolve()),
                    "--apply",
                ],
            )

    def test_apply_stops_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {
                "project": str(root),
                "steps": [
                    {"name": "ok", "command": [sys.executable, "-c", "pass"]},
                    {"name": "fail", "command": [sys.executable, "-c", "raise SystemExit(3)"]},
                    {"name": "never", "command": [sys.executable, "-c", "pass"]},
                ],
            }
            results = self_update.apply_plan(plan)
            self.assertEqual([item["name"] for item in results], ["ok", "fail"])
            self.assertTrue(results[0]["ok"])
            self.assertFalse(results[1]["ok"])
            self.assertEqual(results[1]["exit_code"], 3)


class CommandLineTests(unittest.TestCase):
    def test_json_reports_plan_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "product"
            root.mkdir()
            make_vendored(root, upstream=None)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "self_update.py"),
                    "--project",
                    str(root),
                    "--json",
                    "--cache-dir",
                    str(Path(directory) / "cache"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("kit.upstream.git yok", payload["error"])
            self.assertIn("kit.upstream.git yok", completed.stderr)


class DocTests(unittest.TestCase):
    def test_runbook_modes(self) -> None:
        text = (ROOT / "delivery" / "runbooks" / "update.md").read_text(encoding="utf-8")
        for mode in ("self", "vendored", "submodule"):
            self.assertIn(mode, text)
        self.assertIn("git -C", text)
        self.assertIn("pointer", text)


if __name__ == "__main__":
    unittest.main()
