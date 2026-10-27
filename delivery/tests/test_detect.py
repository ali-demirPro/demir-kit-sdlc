"""Tests for the project fingerprint."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("detect", SCRIPTS / "detect.py")
detect_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(detect_mod)


def write(root: Path, relative: str, text: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class DetectTests(unittest.TestCase):
    def test_web_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "package.json",
                json.dumps(
                    {
                        "dependencies": {"next": "1", "react": "1"},
                        "scripts": {"test": "vitest", "typecheck": "tsc"},
                    }
                ),
            )
            write(root, "next.config.js", "module.exports = {}")
            write(root, "src/app/page.tsx", "export default 1")
            write(root, "vercel.json", "{}")
            data = detect_mod.detect(root)
            self.assertEqual(
                [item["name"] for item in data["surfaces"]], ["web"]
            )
            self.assertEqual(data["surfaces"][0]["platforms"], ["web"])
            self.assertIn("next", [item["name"] for item in data["stacks"]])
            self.assertEqual(data["test_commands"]["behavior"], "npm run test")
            self.assertIn("web_deploy", [item["type"] for item in data["distribution"]])
            self.assertEqual(data["suggested_profile"], "web-app")
            self.assertNotIn(
                "ios", [platform for item in data["surfaces"] for platform in item["platforms"]]
            )
            self.assertNotIn(
                "android",
                [platform for item in data["surfaces"] for platform in item["platforms"]],
            )

    def test_ios_app_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "Package.swift", "// swift-tools-version: 5.9\nimport SwiftUI\n")
            (root / "ios" / "App.xcodeproj").mkdir(parents=True)
            write(root, "fastlane/Fastfile", "app_store\n")
            data = detect_mod.detect(root)
            platforms = [
                platform
                for item in data["surfaces"]
                for platform in item["platforms"]
            ]
            self.assertIn("ios", platforms)
            self.assertEqual(data["suggested_profile"], "ios-app")
            self.assertIn("app_store", [item["type"] for item in data["distribution"]])

    def test_android(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "android/build.gradle", "plugins { id 'com.android.application' }")
            write(root, "android/app/src/main/AndroidManifest.xml", "<manifest/>")
            data = detect_mod.detect(root)
            self.assertEqual(data["surfaces"][0]["platforms"], ["android"])
            self.assertEqual(data["suggested_profile"], "android-app")

    def test_flutter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "pubspec.yaml",
                "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n",
            )
            (root / "ios").mkdir()
            (root / "android").mkdir()
            data = detect_mod.detect(root)
            self.assertEqual(set(data["surfaces"][0]["platforms"]), {"ios", "android"})
            self.assertEqual(data["suggested_profile"], "mobile-app")

    def test_gradle_jvm_is_not_android(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "build.gradle", "plugins { id 'java' }")
            write(root, "src/main/java/App.java", "class App {}")
            data = detect_mod.detect(root)
            self.assertNotIn(
                "android",
                [platform for item in data["surfaces"] for platform in item["platforms"]],
            )

    def test_node_modules_manifest_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "package.json", json.dumps({"dependencies": {"react": "1"}}))
            write(
                root,
                "node_modules/lib/src/main/AndroidManifest.xml",
                "<manifest/>",
            )
            data = detect_mod.detect(root)
            self.assertNotIn(
                "android",
                [platform for item in data["surfaces"] for platform in item["platforms"]],
            )

    def test_plain_dart_is_not_mobile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "pubspec.yaml", "name: tool\ndependencies:\n  args: any\n")
            (root / "bin").mkdir()
            data = detect_mod.detect(root)
            self.assertEqual(data["suggested_profile"], "cli")
            self.assertNotIn(
                "ios",
                [platform for item in data["surfaces"] for platform in item["platforms"]],
            )

    def test_eas_ios_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "eas.json", json.dumps({"build": {"production": {"ios": {}}}}))
            data = detect_mod.detect(root)
            kinds = [item["type"] for item in data["distribution"]]
            self.assertIn("app_store", kinds)
            self.assertNotIn("play_console", kinds)

    def test_python_api_and_risk_hotspot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "pyproject.toml", "[project]\nname='api'\n")
            write(root, "api/main.py", "print('x')")
            write(root, "src/auth/login.py", "print('x')")
            data = detect_mod.detect(root)
            self.assertIn(
                "api",
                [platform for item in data["surfaces"] for platform in item["platforms"]],
            )
            self.assertIn("src/auth", data["risk_hotspots"])
            self.assertEqual(data["suggested_profile"], "api-service")

    def test_pnpm_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "package.json",
                json.dumps(
                    {
                        "dependencies": {"next": "1"},
                        "scripts": {
                            "test": "vitest",
                            "typecheck": "tsc",
                            "lint": "eslint .",
                        },
                    }
                ),
            )
            write(root, "pnpm-lock.yaml", "lockfileVersion: 9\n")
            data = detect_mod.detect(root)
            self.assertEqual(data["test_commands"]["behavior"], "pnpm run test")
            self.assertEqual(data["test_commands"]["typecheck"], "pnpm run typecheck")
            self.assertEqual(data["test_commands"]["lint"], "pnpm run lint")

    def test_python_uv_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "pyproject.toml", "[tool.pytest.ini_options]\n")
            write(root, "uv.lock", "version = 1\n")
            write(root, "app/main.py", "print(1)\n")
            data = detect_mod.detect(root)
            self.assertEqual(data["test_commands"]["behavior"], "uv run pytest")

    def test_nested_flutter_monorepo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "apps/mobile/pubspec.yaml",
                "name: app\nenvironment:\n  sdk: flutter\nflutter:\n  uses-material-design: true\n",
            )
            (root / "apps/mobile/ios").mkdir()
            (root / "apps/mobile/android").mkdir()
            write(root, "apps/mobile/lib/main.dart", "void main() {}\n")
            data = detect_mod.detect(root)
            surface = next(
                item for item in data["surfaces"] if item["path"] == "apps/mobile"
            )
            self.assertEqual(surface["platforms"], ["ios", "android"])
            self.assertIn("flutter", surface["stacks"])
            self.assertIn("apps/mobile", data["app_paths"])
            self.assertEqual(
                data["test_commands"]["behavior"],
                "(cd apps/mobile && flutter test)",
            )

    def test_nested_web_api_monorepo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "web/package.json",
                json.dumps(
                    {
                        "dependencies": {"next": "1", "react": "1"},
                        "scripts": {"test": "vitest"},
                    }
                ),
            )
            write(root, "api/pyproject.toml", "[tool.pytest.ini_options]\n")
            write(root, "api/main.py", "print(1)\n")
            data = detect_mod.detect(root)
            paths = {item["path"] for item in data["surfaces"]}
            self.assertEqual(paths, {"web", "api"})
            self.assertIn("(cd api && pytest)", data["test_commands"]["behavior"])
            self.assertIn("(cd web && npm run test)", data["test_commands"]["behavior"])
            self.assertEqual(data["app_paths"], ["web", "api"])

    def test_nested_node_surfaces_use_own_deps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "apps/web/package.json",
                json.dumps({"dependencies": {"next": "1", "react": "1"}}),
            )
            write(
                root,
                "packages/lib/package.json",
                json.dumps({"dependencies": {"lodash": "1"}}),
            )
            data = detect_mod.detect(root)
            paths = {item["path"] for item in data["surfaces"]}
            self.assertEqual(paths, {"apps/web"})

    def test_nested_xcode_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "apps/ios/App.xcodeproj").mkdir(parents=True)
            data = detect_mod.detect(root)
            surface = next(
                item for item in data["surfaces"] if item["path"] == "apps/ios"
            )
            self.assertEqual(surface["platforms"], ["ios"])
            self.assertIn("swift", surface["stacks"])
            self.assertEqual(
                data["test_commands"]["behavior"], "(cd apps/ios && xcodebuild test)"
            )

    def test_nested_path_with_space_is_quoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "apps/my app/pubspec.yaml",
                "name: app\nenvironment:\n  sdk: flutter\n",
            )
            data = detect_mod.detect(root)
            self.assertEqual(
                data["test_commands"]["behavior"],
                "(cd 'apps/my app' && flutter test)",
            )

    def test_nested_symlink_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "apps/mobile/pubspec.yaml",
                "name: app\nenvironment:\n  sdk: flutter\n",
            )
            (root / "apps/mobile/ios").mkdir()
            (root / "apps/mobile/android").mkdir()
            (root / "mobile").symlink_to(root / "apps/mobile", target_is_directory=True)
            data = detect_mod.detect(root)
            self.assertEqual(len(data["surfaces"]), 1)
            self.assertEqual(data["surfaces"][0]["path"], "apps/mobile")

    def test_nested_flutter_platform_folders_are_not_packages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "mobile/pubspec.yaml",
                "name: app\nenvironment:\n  sdk: flutter\n",
            )
            (root / "mobile/ios/Runner.xcodeproj").mkdir(parents=True)
            (root / "mobile/ios/Podfile").write_text("platform :ios\n")
            (root / "mobile/android").mkdir()
            data = detect_mod.detect(root)
            self.assertEqual(len(data["surfaces"]), 1)
            self.assertEqual(data["surfaces"][0]["path"], "mobile")
            self.assertEqual(data["surfaces"][0]["platforms"], ["ios", "android"])

    def test_nested_ignores_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "node_modules/pkg/package.json",
                json.dumps({"dependencies": {"next": "1"}}),
            )
            data = detect_mod.detect(root)
            self.assertEqual(data["surfaces"], [])

    def test_root_surface_wins_over_nested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "package.json",
                json.dumps({"dependencies": {"next": "1", "react": "1"}}),
            )
            write(
                root,
                "apps/mobile/pubspec.yaml",
                "name: app\nenvironment:\n  sdk: flutter\n",
            )
            data = detect_mod.detect(root)
            self.assertEqual(len(data["surfaces"]), 1)
            self.assertEqual(data["surfaces"][0]["path"], ".")

    def test_detect_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "package.json", json.dumps({"dependencies": {"react": "1"}}))
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            detect_mod.detect(root)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
