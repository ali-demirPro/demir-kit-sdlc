#!/usr/bin/env python3
"""MCP self-check for doctor: spawn the read-only server and validate its tools."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MCP_TOOLS = ("status", "brief", "doctor", "next_leaf_list", "guard", "explain")


def check_mcp_self(root: Path, script: Path | None = None) -> list[str]:
    """MCP sunucusunu başlatıp `tools/list` yanıtını doğrular.

    Ağ yok; yalnız stdio. Hata fırlatmaz, kısa Türkçe mesaj listesi döner.
    """
    script = script or root / "delivery" / "scripts" / "mcp_server.py"
    if not script.is_file():
        return ["mcp: mcp_server.py yok"]
    request = "\n".join(
        (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "doctor", "version": "1"},
                    },
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        )
    ) + "\n"
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script), "--project", str(root)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:  # pragma: no cover - platforma bağlı
        return [f"mcp: sunucu başlatılamadı — {exc}"]
    try:
        stdout, stderr = proc.communicate(request, timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return ["mcp: sunucu 10 sn içinde yanıt vermedi"]

    initialized = False
    tools = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        if message.get("id") == 1 and isinstance(message.get("result"), dict):
            initialized = True
        if message.get("id") == 2:
            result = message.get("result")
            tools = result.get("tools") if isinstance(result, dict) else None
    errors: list[str] = []
    if not initialized:
        errors.append("mcp: initialize yanıtı yok")
    if not isinstance(tools, list):
        tail = " ".join((stderr or "").strip().splitlines()[-3:])[:200]
        suffix = f" — {tail}" if tail else ""
        return errors + [f"mcp: tools/list yanıtı yok{suffix}"]

    names = [
        str(tool.get("name"))
        for tool in tools
        if isinstance(tool, dict) and tool.get("name")
    ]
    errors += [
        f"mcp: eksik araç — {name}" for name in MCP_TOOLS if name not in names
    ]
    errors += [
        f"mcp: beklenmeyen araç — {name}" for name in sorted(set(names) - set(MCP_TOOLS))
    ]
    if len(names) != len(MCP_TOOLS):
        errors.append(f"mcp: araç sayısı {len(names)} ≠ {len(MCP_TOOLS)}")
    if len(set(names)) != len(names):
        errors.append("mcp: araç adları tekrarlı")
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("name") not in MCP_TOOLS:
            continue
        annotations = tool.get("annotations")
        if not (
            isinstance(annotations, dict) and annotations.get("readOnlyHint") is True
        ):
            errors.append(f"mcp: {tool.get('name')} readOnlyHint true değil")
        if not isinstance(tool.get("inputSchema"), dict):
            errors.append(f"mcp: {tool.get('name')} inputSchema yok")
    return errors
