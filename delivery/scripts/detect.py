#!/usr/bin/env python3
"""Read-only project fingerprint for demir-kit adaptation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RISK_NAMES = ("auth", "payments", "billing", "migrations", "security")
APP_DIRS = ("src", "app", "lib", "web", "api", "server", "ios", "android", "packages")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def detect(project: Path) -> dict:
    root = project.resolve()
    stacks: dict[str, dict] = {}
    surfaces: dict[str, dict] = {}
    distribution: dict[str, dict] = {}
    tests: dict[str, str] = {}
    evidence: list[str] = []

    def add_stack(name: str, source: str, confidence: float = 0.9) -> None:
        item = stacks.setdefault(
            name, {"name": name, "confidence": confidence, "evidence": []}
        )
        if source not in item["evidence"]:
            item["evidence"].append(source)
        item["confidence"] = max(item["confidence"], confidence)

    def add_surface(
        name: str,
        path: str,
        platforms: list[str],
        surface_stacks: list[str],
        source: str,
        confidence: float = 0.8,
    ) -> None:
        item = surfaces.setdefault(
            name,
            {
                "name": name,
                "path": path,
                "platforms": [],
                "stacks": [],
                "confidence": confidence,
                "evidence": [],
            },
        )
        for platform in platforms:
            if platform not in item["platforms"]:
                item["platforms"].append(platform)
        for stack in surface_stacks:
            if stack not in item["stacks"]:
                item["stacks"].append(stack)
        if source not in item["evidence"]:
            item["evidence"].append(source)
        item["confidence"] = max(item["confidence"], confidence)

    def add_distribution(kind: str, source: str, confidence: float = 0.8) -> None:
        item = distribution.setdefault(
            kind, {"type": kind, "confidence": confidence, "evidence": []}
        )
        if source not in item["evidence"]:
            item["evidence"].append(source)
        item["confidence"] = max(item["confidence"], confidence)

    pubspec_text = read_text(root / "pubspec.yaml")
    has_flutter = (root / "pubspec.yaml").is_file() and (
        "sdk: flutter" in pubspec_text or "\nflutter:" in "\n" + pubspec_text
    )

    # Node / web
    package_path = root / "package.json"
    package = read_json(package_path)
    deps = {}
    if package:
        deps.update(package.get("dependencies") or {})
        deps.update(package.get("devDependencies") or {})
        evidence.append("package.json")
        mapping = {
            "next": "next",
            "react": "react",
            "react-dom": "react",
            "react-native": "react-native",
            "expo": "expo",
            "vue": "vue",
            "svelte": "svelte",
            "vite": "vite",
            "typescript": "typescript",
            "express": "express",
            "fastify": "fastify",
            "@nestjs/core": "nestjs",
            "@capacitor/core": "capacitor",
        }
        for dep, stack in mapping.items():
            if dep in deps:
                add_stack(stack, f"package.json: {dep}")
        scripts = package.get("scripts") or {}
        if "test" in scripts:
            tests["behavior"] = "npm test"
        if "typecheck" in scripts:
            tests["typecheck"] = "npm run typecheck"
        if "lint" in scripts:
            tests["lint"] = "npm run lint"
        web_stacks = [
            stack
            for stack in ("next", "react", "vue", "svelte", "vite")
            if stack in stacks
        ]
        if web_stacks:
            add_surface("web", ".", ["web"], web_stacks, "package.json")
        if "express" in stacks or "fastify" in stacks or "nestjs" in stacks:
            add_surface(
                "api",
                "api" if (root / "api").is_dir() else ".",
                ["api"],
                [stack for stack in ("express", "fastify", "nestjs") if stack in stacks],
                "package.json",
            )
        if package.get("bin"):
            add_surface("cli", ".", ["cli"], ["node"], "package.json: bin")

    for name in ("next.config.js", "next.config.mjs", "next.config.ts"):
        if (root / name).is_file():
            add_stack("next", name)
    for name in ("vite.config.js", "vite.config.ts", "vite.config.mjs"):
        if (root / name).is_file():
            add_stack("vite", name)
    if (root / "tsconfig.json").is_file():
        add_stack("typescript", "tsconfig.json")

    # Swift / iOS
    swift_sources = []
    for name in ("Package.swift", "Podfile"):
        if (root / name).is_file():
            swift_sources.append(name)
    xcodeproj = list(root.glob("*.xcodeproj")) + list(root.glob("ios/*.xcodeproj"))
    swift_sources += [rel(path, root) for path in xcodeproj]
    if swift_sources and not has_flutter:
        text = " ".join(
            read_text(root / name)
            for name in ("Package.swift", "Podfile")
            if (root / name).is_file()
        )
        add_stack("swift", swift_sources[0])
        if "SwiftUI" in text or any((root / "ios").rglob("*.swift")):
            add_stack("swiftui", "swift sources")
        if "UIKit" in text:
            add_stack("uikit", "swift sources")
        add_surface(
            "ios",
            "ios" if (root / "ios").is_dir() else ".",
            ["ios"],
            [stack for stack in ("swift", "swiftui", "uikit") if stack in stacks],
            swift_sources[0],
        )
        tests.setdefault(
            "behavior", "swift test" if (root / "Package.swift").is_file() else "xcodebuild test"
        )

    # Android: a root build.gradle alone is not enough (JVM/Spring is common).
    gradle = list(root.glob("build.gradle*")) + list(root.glob("android/build.gradle*"))
    manifests = []
    candidates = [
        root / "android" / "app" / "src" / "main" / "AndroidManifest.xml",
        root / "app" / "src" / "main" / "AndroidManifest.xml",
        root / "src" / "main" / "AndroidManifest.xml",
    ]
    manifests = [path for path in candidates if path.is_file()]
    if not manifests:
        for path in root.glob("*/src/main/AndroidManifest.xml"):
            if not set(path.parts) & {"node_modules", "build", ".git", "vendor", "Pods"}:
                manifests.append(path)
    gradle_text = " ".join(read_text(path) for path in gradle)
    android = bool(manifests) or (root / "android").is_dir() or "com.android" in gradle_text
    if gradle:
        add_stack("gradle", rel(gradle[0], root))
    if android and not has_flutter:
        source = (
            rel(manifests[0], root)
            if manifests
            else (rel(gradle[0], root) if gradle else "android")
        )
        add_stack("kotlin", source)
        if "compose" in gradle_text.lower():
            add_stack("compose", source)
        add_surface(
            "android",
            "android" if (root / "android").is_dir() else ".",
            ["android"],
            [stack for stack in ("kotlin", "compose") if stack in stacks],
            source,
        )
        tests.setdefault("behavior", "./gradlew test")

    # Flutter: plain Dart packages are not mobile.
    if (root / "pubspec.yaml").is_file():
        text = pubspec_text
        flutter = has_flutter
        if flutter:
            add_stack("flutter", "pubspec.yaml")
            add_stack("dart", "pubspec.yaml")
            platforms = [
                platform
                for platform in ("ios", "android", "web")
                if (root / platform).is_dir()
            ] or ["ios", "android"]
            add_surface("mobile", ".", platforms, ["flutter"], "pubspec.yaml")
            tests.setdefault("behavior", "flutter test")
        else:
            add_stack("dart", "pubspec.yaml")
            if (root / "bin").is_dir():
                add_surface("cli", ".", ["cli"], ["dart"], "pubspec.yaml: bin")

    # Python / API
    python_files = [
        name
        for name in ("pyproject.toml", "requirements.txt", "setup.py", "manage.py")
        if (root / name).is_file()
    ]
    if python_files:
        text = " ".join(read_text(root / name) for name in python_files)
        add_stack("python", python_files[0])
        if "django" in text.lower() or (root / "manage.py").is_file():
            add_stack("django", "python metadata")
        if "fastapi" in text.lower():
            add_stack("fastapi", "python metadata")
        api_path = "api" if (root / "api").is_dir() else (
            "server" if (root / "server").is_dir() else "."
        )
        add_surface(
            "api",
            api_path,
            ["api"],
            [stack for stack in ("python", "django", "fastapi") if stack in stacks],
            python_files[0],
        )
        tests.setdefault("behavior", "pytest")

    # Docker / CI / distribution
    if (root / "Dockerfile").is_file():
        add_stack("docker", "Dockerfile")
    if (root / "docker-compose.yml").is_file() or (root / "compose.yaml").is_file():
        add_stack("docker", "docker-compose.yml")

    if (root / "vercel.json").is_file():
        add_distribution("web_deploy", "vercel.json")
    if (root / "netlify.toml").is_file():
        add_distribution("web_deploy", "netlify.toml")
    if (root / "fly.toml").is_file():
        add_distribution("web_deploy", "fly.toml")
    if (root / "eas.json").is_file():
        text = read_text(root / "eas.json").lower()
        if "ios" in text:
            add_distribution("app_store", "eas.json: ios")
        if "android" in text:
            add_distribution("play_console", "eas.json: android")
        if "ios" not in text and "android" not in text:
            add_distribution("app_store", "eas.json")
            add_distribution("play_console", "eas.json")

    workflows = list((root / ".github" / "workflows").glob("*.yml")) + list(
        (root / ".github" / "workflows").glob("*.yaml")
    )
    for workflow in workflows:
        text = read_text(workflow).lower()
        source = rel(workflow, root)
        if "app_store" in text or "testflight" in text:
            add_distribution("app_store", source)
        if "play console" in text or "play_console" in text or "google play" in text:
            add_distribution("play_console", source)
        if any(word in text for word in ("deploy", "vercel", "netlify", "production")):
            add_distribution("web_deploy", source)
        if "release" in source.lower() or "release" in text:
            add_distribution("release", source)

    fastlane = root / "fastlane" / "Fastfile"
    if fastlane.is_file():
        text = read_text(fastlane).lower()
        if "app_store" in text or "testflight" in text:
            add_distribution("app_store", "fastlane/Fastfile")
        if "supply" in text or "play" in text:
            add_distribution("play_console", "fastlane/Fastfile")

    app_paths = [name for name in APP_DIRS if (root / name).is_dir()]
    hotspots: list[str] = []
    for base in app_paths or ["."]:
        base_path = root / base
        for path in base_path.rglob("*"):
            if len(hotspots) >= 50:
                break
            if path.is_dir() and path.name.lower() in RISK_NAMES:
                hotspots.append(rel(path, root))
    hotspots = sorted(dict.fromkeys(hotspots))

    platforms = sorted(
        {platform for item in surfaces.values() for platform in item["platforms"]}
    )
    if "ios" in platforms and "android" in platforms:
        suggested = "mobile-app"
    elif "ios" in platforms:
        suggested = "ios-app"
    elif "android" in platforms:
        suggested = "android-app"
    elif "web" in platforms:
        suggested = "web-product"
    elif "api" in platforms:
        suggested = "api-service"
    elif "cli" in platforms:
        suggested = "cli"
    else:
        suggested = "unknown"

    return {
        "project": str(root),
        "stacks": [
            item for item in sorted(stacks.values(), key=lambda value: value["name"])
        ],
        "surfaces": [
            item for item in sorted(surfaces.values(), key=lambda value: value["name"])
        ],
        "distribution": [
            item
            for item in sorted(distribution.values(), key=lambda value: value["type"])
        ],
        "test_commands": tests,
        "app_paths": app_paths,
        "risk_hotspots": hotspots,
        "suggested_profile": suggested,
        "evidence": sorted(dict.fromkeys(evidence)),
    }


def render(data: dict) -> str:
    lines = [
        f"project: {data['project']}",
        f"profile: {data['suggested_profile']}",
        "stacks: " + (", ".join(item["name"] for item in data["stacks"]) or "-"),
    ]
    for surface in data["surfaces"]:
        lines.append(
            f"surface {surface['name']}: {surface['path']} "
            f"[{', '.join(surface['platforms'])}] "
            f"({', '.join(surface['stacks'])})"
        )
    for item in data["distribution"]:
        lines.append(f"distribution {item['type']}: {', '.join(item['evidence'])}")
    for key, value in data["test_commands"].items():
        lines.append(f"test {key}: {value}")
    lines.append("app paths: " + (", ".join(data["app_paths"]) or "-"))
    lines.append("risk hotspots: " + (", ".join(data["risk_hotspots"]) or "-"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="read-only project fingerprint")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = detect(args.project)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
