"""Tests for the read-only stdio MCP server (JSON-RPC core, CP-1)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "delivery" / "scripts" / "mcp_server.py"
TOOL_NAMES = {"status", "brief", "doctor", "next_leaf_list", "guard"}


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proc: subprocess.Popen[str] | None = None

    def tearDown(self) -> None:
        if self.proc is None:
            return
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        finally:
            for stream in (self.proc.stdout, self.proc.stderr):
                if stream:
                    stream.close()

    def start(self, *extra: str, cwd: Path = ROOT) -> subprocess.Popen[str]:
        """Sunucuyu subprocess olarak başlatır."""
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), *extra],
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return self.proc

    def send(self, payload: object) -> dict | None:
        """Bir satır yazar; yanıt satırını JSON olarak okur."""
        assert self.proc is not None and self.proc.stdin and self.proc.stdout
        line = payload if isinstance(payload, str) else json.dumps(payload)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        reply = self.proc.stdout.readline()
        if not reply:
            return None
        return json.loads(reply)

    def test_initialize_and_tools_list(self) -> None:
        self.start("--project", str(ROOT))
        init = self.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        assert init is not None
        result = init["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "demir-kit")
        self.assertTrue(result["serverInfo"]["version"])

        # Bildirim yanıt üretmez: sıradaki satır doğrudan tools/list yanıtıdır.
        assert self.proc is not None and self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self.proc.stdin.flush()

        listed = self.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert listed is not None
        tools = listed["result"]["tools"]
        self.assertEqual({item["name"] for item in tools}, TOOL_NAMES)
        self.assertEqual(len(tools), len(TOOL_NAMES))
        for item in tools:
            self.assertEqual(item["annotations"], {"readOnlyHint": True})
            self.assertTrue(item["title"])
            self.assertTrue(item["description"])
            self.assertEqual(item["inputSchema"]["type"], "object")

    def test_project_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcp-no-project-") as tmp:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=tmp,
                input="",
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("proje", proc.stderr.lower())
        self.assertEqual(proc.stdout.strip(), "")

    def test_unknown_method_and_bad_json(self) -> None:
        self.start("--project", str(ROOT))
        unknown = self.send({"jsonrpc": "2.0", "id": 3, "method": "tools/nope"})
        assert unknown is not None
        self.assertEqual(unknown["error"]["code"], -32601)

        broken = self.send('{"jsonrpc": "2.0", "id": 4, "method": ')
        assert broken is not None
        self.assertEqual(broken["error"]["code"], -32602)

        # Süreç yaşıyor: sonraki istek hâlâ yanıtlanır.
        alive = self.send({"jsonrpc": "2.0", "id": 5, "method": "ping"})
        assert alive is not None
        self.assertEqual(alive["result"], {})
        assert self.proc is not None
        self.assertIsNone(self.proc.poll(), "sunucu süreci yaşamalı")

        tolerated = self.send({"jsonrpc": "2.0", "id": 6, "method": "initialize", "params": "x"})
        assert tolerated is not None
        self.assertEqual(tolerated["error"]["code"], -32602)


class ProtocolVersionTests(unittest.TestCase):
    def test_unsupported_version_falls_back(self) -> None:
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--project", str(ROOT)],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "1999-01-01"},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            reply = json.loads(proc.stdout.readline())
            self.assertEqual(reply["result"]["protocolVersion"], "2024-11-05")
        finally:
            if proc.stdin:
                proc.stdin.close()
            proc.wait(timeout=5)
            for stream in (proc.stdout, proc.stderr):
                if stream:
                    stream.close()


if __name__ == "__main__":
    unittest.main()
