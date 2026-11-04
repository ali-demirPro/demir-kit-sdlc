"""doctor MCP self-check (issue #179).

Run: python3 -m unittest delivery.tests.test_doctor_mcp -v
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"

spec = importlib.util.spec_from_file_location("doctor_mcp", SCRIPTS / "doctor_mcp.py")
doctor_mcp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(doctor_mcp)

FAKE_SERVER = '''\
"""Test için sahte MCP sunucusu: iki satır soruya iki satır yanıt."""

import json
import sys

TOOLS = ("status", "brief", "doctor", "next_leaf_list", "guard")

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        print(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake", "version": "1"},
                    },
                }
            ),
            flush=True,
        )
    elif method == "tools/list":
        tools = [
            {
                "name": name,
                "inputSchema": {"type": "object"},
                "annotations": {"readOnlyHint": True},
            }
            for name in TOOLS
        ]
        print(
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": tools}}),
            flush=True,
        )
'''


class SelfCheckTests(unittest.TestCase):
    def test_ok_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "delivery" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "mcp_server.py").write_text(FAKE_SERVER, encoding="utf-8")
            self.assertEqual(doctor_mcp.check_mcp_self(root), [])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "delivery" / "scripts" / "mcp_server.py"
            self.assertEqual(
                doctor_mcp.check_mcp_self(root), ["mcp: mcp_server.py yok"]
            )
            self.assertEqual(
                doctor_mcp.check_mcp_self(root, missing), ["mcp: mcp_server.py yok"]
            )


class RealServerTests(unittest.TestCase):
    def test_real_server_passes(self) -> None:
        """Gerçek mcp_server.py beş aracı ve inputSchema'yı sağlar."""
        errors = doctor_mcp.check_mcp_self(ROOT)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
