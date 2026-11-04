"""Tests for the read-only stdio MCP server (JSON-RPC core, tools, read-only)."""

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
FORBIDDEN = {"transition", "claim", "update", "seal"}


def snapshot(root: Path) -> set[str]:
    """Proje dosyaları; `.orchestration/` dışarıda (önbellek alanı)."""
    found: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == ".orchestration":
            continue
        found.add(str(relative))
    return found


class ServerTestCase(unittest.TestCase):
    proc: subprocess.Popen[str] | None = None

    def make_project(self, tmp: str) -> Path:
        """Kit kökünü işaret eden geçici proje (kit.config.yaml)."""
        project = Path(tmp)
        (project / "kit.config.yaml").write_text(
            f"kit:\n  root: {ROOT}\n  version: 2.56.0\n", encoding="utf-8"
        )
        return project

    def setUp(self) -> None:
        self.proc = None

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

    def call_tool(self, name: str, arguments: object = None, msg_id: int = 10) -> dict:
        """tools/call yazar; yanıt zarfını döner."""
        params: dict = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments
        reply = self.send({"jsonrpc": "2.0", "id": msg_id, "method": "tools/call", "params": params})
        assert reply is not None
        return reply


class ProtocolTests(ServerTestCase):
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
        self.assertEqual(broken["error"]["code"], -32700)

        not_object = self.send([1, 2, 3])
        assert not_object is not None
        self.assertEqual(not_object["error"]["code"], -32600)

        # Süreç yaşıyor: sonraki istek hâlâ yanıtlanır.
        alive = self.send({"jsonrpc": "2.0", "id": 5, "method": "ping"})
        assert alive is not None
        self.assertEqual(alive["result"], {})
        assert self.proc is not None
        self.assertIsNone(self.proc.poll(), "sunucu süreci yaşamalı")

        tolerated = self.send({"jsonrpc": "2.0", "id": 6, "method": "initialize", "params": "x"})
        assert tolerated is not None
        self.assertEqual(tolerated["error"]["code"], -32602)


class ToolTests(ServerTestCase):
    def test_status_call(self) -> None:
        """Çevrimdışı status geçerli JSON metni ve contract_version döner."""
        self.start("--project", str(ROOT))
        reply = self.call_tool("status", {"offline": True})
        result = reply["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(len(result["content"]), 1)
        self.assertEqual(result["content"][0]["type"], "text")
        text = result["content"][0]["text"]
        self.assertIn("contract_version", text)
        data = json.loads(text)
        self.assertIn("contract_version", data)

    def test_errors(self) -> None:
        """Eksik/yanlış argüman ve bilinmeyen araç -32602; süreç yaşar."""
        self.start("--project", str(ROOT))
        missing = self.call_tool("brief", {}, msg_id=11)
        self.assertEqual(missing["error"]["code"], -32602)
        self.assertIn("issue", missing["error"]["message"])

        wrong_type = self.call_tool("brief", {"issue": "on"}, msg_id=12)
        self.assertEqual(wrong_type["error"]["code"], -32602)

        unknown_argument = self.call_tool("status", {"nope": True}, msg_id=13)
        self.assertEqual(unknown_argument["error"]["code"], -32602)

        missing_argument = self.call_tool("guard", None, msg_id=14)
        self.assertEqual(missing_argument["error"]["code"], -32602)

        unknown_tool = self.call_tool("transition", {"issue": 1}, msg_id=16)
        self.assertEqual(unknown_tool["error"]["code"], -32602)
        self.assertIn("bilinmeyen araç", unknown_tool["error"]["message"])

        alive = self.send({"jsonrpc": "2.0", "id": 17, "method": "ping"})
        assert alive is not None
        self.assertEqual(alive["result"], {})
        assert self.proc is not None
        self.assertIsNone(self.proc.poll(), "sunucu süreci yaşamalı")


class ToolReadOnlyAlias:
    """T-5 kimliği ToolTests altında; gövde ReadOnlyTests ile aynı."""


class ReadOnlyTests(ServerTestCase):
    def test_read_only_tools(self) -> None:
        """Yasak mutasyon araçları yok, hepsi salt-okunur; status dosya yazmaz."""
        with tempfile.TemporaryDirectory(prefix="mcp-ro-") as tmp:
            project = self.make_project(tmp)
            self.start("--project", str(project))
            listed = self.send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            assert listed is not None
            tools = listed["result"]["tools"]
            names = {item["name"] for item in tools}
            self.assertEqual(names, TOOL_NAMES)
            self.assertFalse(names & FORBIDDEN, f"mutasyon aracı listelendi: {names & FORBIDDEN}")
            for item in tools:
                self.assertIs(item["annotations"].get("readOnlyHint"), True)
                self.assertNotIn(item["name"], FORBIDDEN)

            before = snapshot(project)
            reply = self.call_tool("status", {"offline": True}, msg_id=2)
            self.assertFalse(reply["result"]["isError"])
            self.assertIn("contract_version", reply["result"]["content"][0]["text"])
            self.assertEqual(snapshot(project), before, "status yeni dosya yazmamalı")

    def test_status_is_read_only(self) -> None:
        """status öncesi/sonrası dosya listesi aynı; önbellek yazılmıyor."""
        with tempfile.TemporaryDirectory(prefix="mcp-status-") as tmp:
            project = self.make_project(tmp)
            before = snapshot(project)
            self.start("--project", str(project))
            reply = self.call_tool("status", {"offline": True}, msg_id=3)
            self.assertFalse(reply["result"]["isError"])
            self.assertEqual(snapshot(project), before)
            self.assertFalse(
                (project / ".orchestration" / "status-cache.json").exists(),
                "--cache-ttl verilmediği için önbellek yazılmamalı",
            )


ToolTests.test_read_only_tools = ReadOnlyTests.test_read_only_tools


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
