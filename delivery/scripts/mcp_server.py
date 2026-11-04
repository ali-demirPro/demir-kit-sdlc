#!/usr/bin/env python3
"""Salt-okunur MCP sunucusu: kit komutlarını stdio üzerinden JSON-RPC 2.0 ile sunar.

Protokol:
- stdio; her satır bir JSON-RPC 2.0 mesajı, her yanıt tek satır JSON.
- `initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`.
- Bozuk JSON ve bozuk params `-32602`, bilinmeyen metot `-32601` döner; süreç düşmez.

`tools/call` mevcut kit komutlarını alt süreç olarak koşar (cwd = proje,
120 sn zaman aşımı, stdout+stderr birleşik); hiçbir araç yazma yapmaz.
Eksik/yanlış argüman ve bilinmeyen araç `-32602` döner.
Çıktı 20.000 karakterde kırpılır ve not düşülür.

Proje çözümü: `--project PATH` ya da cwd'de `kit.config.yaml`. Kit kökü
`kit.config.yaml: kit.root`, yoksa yukarı doğru `delivery/scripts/doctor.py|doctor.sh`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SERVER_NAME = "demir-kit"
CONFIG_NAME = "kit.config.yaml"
KIT_MARKERS = (
    Path("delivery") / "scripts" / "doctor.py",
    Path("delivery") / "scripts" / "doctor.sh",
)
SUPPORTED_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
DEFAULT_PROTOCOL = "2024-11-05"

# JSON-RPC 2.0 hata kodları.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

MAX_TEXT = 20_000
MAX_LINE = 1_048_576
TRUNCATED_NOTE = "… (kırpıldı)"
TOOL_TIMEOUT = 120


def tool(name: str, title: str, description: str, schema: dict) -> dict:
    """MCP araç tanımı; hepsi salt-okunur."""
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": schema,
        "annotations": {"readOnlyHint": True},
    }


def object_schema(properties: dict | None = None, required: list[str] | None = None) -> dict:
    schema: dict = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False
    return schema


ISSUE_SCHEMA = object_schema(
    {
        "issue": {
            "type": "integer",
            "minimum": 1,
            "description": "GitHub issue (leaf) numarası.",
        }
    },
    ["issue"],
)

TOOLS = [
    tool(
        "status",
        "Proje durumu",
        "Proje ve epic durumunu salt-okunur özetler; fleet genel bakışı verir.",
        object_schema(
            {
                "project": {
                    "type": "string",
                    "description": "Durumu okunacak proje dizini (varsayılan: sunucu projesi).",
                },
                "offline": {
                    "type": "boolean",
                    "description": "Ağa çıkmadan önbellekten döner.",
                },
                "with_gate": {
                    "type": "boolean",
                    "description": "Epic başına doctor gate'ini de koşar.",
                },
                "with_cost": {
                    "type": "boolean",
                    "description": "Maliyet özetini de ekler.",
                },
            }
        ),
    ),
    tool(
        "brief",
        "Leaf brief",
        "Bir leaf issue için ajan brief'ini döner; rol, kapsam ve kabul kriterleri.",
        object_schema(
            {
                "issue": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "GitHub issue (leaf) numarası.",
                },
                "cp": {
                    "type": "string",
                    "description": "Yalnız bu checkpoint için kompakt brief, örn. CP-1.",
                },
            },
            ["issue"],
        ),
    ),
    tool(
        "doctor",
        "Doctor gate",
        "Statik doğrulamayı koşar ve issue/checkpoint için kapı sonucunu döner.",
        object_schema(
            {
                "issue": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "GitHub issue (leaf) numarası.",
                },
                "checkpoint": {
                    "type": "string",
                    "description": "Checkpoint id, örn. CP-1.",
                },
                "strict": {
                    "type": "boolean",
                    "description": "Uyarıları da hata say.",
                },
            }
        ),
    ),
    tool(
        "next_leaf_list",
        "Sıradaki leaf'ler",
        "Bağımlılık sırasına göre hazır leaf kuyruğunu listeler; claim yapmaz.",
        object_schema(),
    ),
    tool(
        "guard",
        "Kaynak kapısı",
        "Bir issue için kaynak değişikliği kapısını (worktree + risk) salt-okunur denetler.",
        ISSUE_SCHEMA,
    ),
]

TOOL_BY_NAME = {item["name"]: item for item in TOOLS}


class ServerError(Exception):
    """Kullanıcıya stderr ile anlatılan kurulum hatası."""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def parse_minimal_config(text: str) -> dict:
    """YAML yoksa `kit:` bloğundan root/version okuyan küçük ayrıştırıcı."""
    config: dict = {}
    kit: dict = {}
    in_kit = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            in_kit = line.strip() == "kit:"
            continue
        if not in_kit or ":" not in line:
            continue
        key, _, value = line.strip().partition(":")
        if key in {"root", "version"}:
            kit[key] = value.strip().strip("\"'")
    if kit:
        config["kit"] = kit
    return config


def load_config(project: Path) -> dict:
    """`kit.config.yaml`; PyYAML varsa onunla, yoksa minimal ayrıştırıcıyla."""
    path = project / CONFIG_NAME
    text = read_text(path)
    if not text:
        return {}
    try:
        import yaml
    except ImportError:
        return parse_minimal_config(text)
    try:
        data = yaml.safe_load(text)
    except Exception:
        return parse_minimal_config(text)
    return data if isinstance(data, dict) else {}


def section(config: dict, key: str) -> dict:
    value = config.get(key)
    return value if isinstance(value, dict) else {}


def find_kit_root(start: Path, config: dict) -> Path | None:
    """Kit kökü: önce `kit.root`, sonra yukarı doğru doctor işaretçileri."""
    declared = str(section(config, "kit").get("root") or "").strip()
    if declared:
        candidate = Path(declared).expanduser()
        if not candidate.is_absolute():
            candidate = start / candidate
        candidate = candidate.resolve()
        if any((candidate / marker).is_file() for marker in KIT_MARKERS):
            return candidate
    for candidate in (start, *start.parents):
        if any((candidate / marker).is_file() for marker in KIT_MARKERS):
            return candidate
    return None


def resolve_project(explicit: Path | None, cwd: Path) -> Path:
    """--project → o dizin; yoksa cwd'de kit.config.yaml; ikisi de yoksa hata."""
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not candidate.is_dir():
            raise ServerError(f"proje dizini yok: {candidate}")
        return candidate
    if (cwd / CONFIG_NAME).is_file():
        return cwd
    raise ServerError(
        "proje bulunamadı: --project PATH verin ya da kit.config.yaml olan bir "
        f"dizinde çalışın (şu an: {cwd})"
    )


def kit_version(kit_root: Path | None, config: dict) -> str:
    if kit_root is not None:
        version = read_text(kit_root / "VERSION")
        if version:
            return version
    declared = str(section(config, "kit").get("version") or "").strip()
    return declared or "0.0.0"


def resolve_runtime() -> dict:
    """Alt süreçlerde kullanılacak yorumlayıcı ve kabuk yolları."""
    python = shutil.which("python3") or sys.executable
    bash = shutil.which("bash") or "/bin/bash"
    return {"python": python, "bash": bash}


def rpc_ok(msg_id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def rpc_error(msg_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def truncate_output(text: str) -> str:
    if len(text) <= MAX_TEXT:
        return text
    return text[:MAX_TEXT] + "\n" + TRUNCATED_NOTE


JSON_TYPES = {
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
    "object": dict,
    "array": list,
}


def validate_arguments(schema: dict, arguments: object) -> dict:
    """Küçük JSON Schema denetimi: tip, zorunlu alan, minimum, fazladan anahtar."""
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments bir nesne olmalı")
    properties = schema.get("properties") or {}
    for key in arguments:
        if key not in properties:
            raise ValueError(f"bilinmeyen argüman: {key}")
    for key in schema.get("required") or []:
        if key not in arguments:
            raise ValueError(f"{key} zorunlu")
    for key, value in arguments.items():
        spec = properties[key] if isinstance(properties[key], dict) else {}
        expected = spec.get("type")
        python_type = JSON_TYPES.get(expected)
        if python_type is not None:
            if isinstance(value, bool) and expected != "boolean":
                raise ValueError(f"{key} {expected} olmalı")
            if not isinstance(value, python_type):
                raise ValueError(f"{key} {expected} olmalı")
        minimum = spec.get("minimum")
        if isinstance(minimum, int) and isinstance(value, int) and not isinstance(value, bool):
            if value < minimum:
                raise ValueError(f"{key} en az {minimum} olmalı")
    return arguments


class McpServer:
    """stdio JSON-RPC çekirdeği; süreç hiçbir mesajda düşmez."""

    def __init__(self, project: Path, kit_root: Path | None, config: dict) -> None:
        self.project = project
        self.kit_root = kit_root
        self.config = config
        self.version = kit_version(kit_root, config)
        self.runtime = resolve_runtime()
        self.protocol_version = DEFAULT_PROTOCOL

    def initialize(self, params: dict) -> dict:
        requested = params.get("protocolVersion") if isinstance(params, dict) else None
        if requested in SUPPORTED_PROTOCOLS:
            self.protocol_version = str(requested)
        else:
            self.protocol_version = DEFAULT_PROTOCOL
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": self.version},
        }

    def call_tool(self, params: object) -> dict:
        """Araç çağrısı: bilinmeyen ad ve bozuk argüman JSON-RPC hatası."""
        if not isinstance(params, dict):
            raise ValueError("params bir nesne olmalı")
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("name zorunlu")
        spec = TOOL_BY_NAME.get(name)
        if spec is None:
            raise LookupError(f"bilinmeyen araç: {name}")
        arguments = validate_arguments(spec["inputSchema"], params.get("arguments"))
        return self.run_tool(name, arguments)

    def scripts_dir(self) -> Path:
        """Kit scriptleri: kit kökü, yoksa bu dosyanın yanı."""
        if self.kit_root is not None:
            return self.kit_root / "delivery" / "scripts"
        return Path(__file__).resolve().parent

    def status_project(self, arguments: dict) -> Path:
        """`status.project` verilmişse projeye göre çöz, yoksa sunucu projesi."""
        raw = arguments.get("project")
        if not raw:
            return self.project
        candidate = Path(str(raw)).expanduser()
        if not candidate.is_absolute():
            candidate = self.project / candidate
        return candidate

    def build_command(self, name: str, arguments: dict) -> list[str]:
        """Araç adını salt-okunur kit komutuna çevirir."""
        scripts = self.scripts_dir()
        python = self.runtime["python"]
        bash = self.runtime["bash"]
        if name == "status":
            command = [python, str(scripts / "status.py"), "--json"]
            if arguments.get("offline"):
                command.append("--offline")
            if arguments.get("with_gate"):
                command.append("--with-gate")
            if arguments.get("with_cost"):
                command.append("--with-cost")
            command += ["--project", str(self.status_project(arguments))]
            return command
        if name == "brief":
            command = [python, str(scripts / "brief.py"), str(arguments["issue"]), "--json"]
            if arguments.get("cp"):
                command += ["--cp", str(arguments["cp"])]
            return command
        if name == "doctor":
            command = [bash, str(scripts / "doctor.sh")]
            if arguments.get("issue") is not None:
                command += ["--issue", str(arguments["issue"])]
            if arguments.get("checkpoint"):
                command += ["--checkpoint", str(arguments["checkpoint"])]
            if arguments.get("strict"):
                command.append("--strict")
            return command
        if name == "next_leaf_list":
            return [python, str(scripts / "next-leaf.py"), "--list", "--json"]
        if name == "guard":
            return [bash, str(scripts / "guard.sh"), "--issue", str(arguments["issue"])]
        raise ValueError(f"bilinmeyen araç: {name}")

    def run_tool(self, name: str, arguments: dict) -> dict:
        """Alt süreç: cwd = proje, 120 sn, stdout+stderr birleşik."""
        command = self.build_command(name, arguments)
        try:
            proc = subprocess.run(
                command,
                cwd=str(self.project),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TOOL_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {
                "content": [
                    {"type": "text", "text": f"{name}: {TOOL_TIMEOUT} sn zaman aşımı"}
                ],
                "isError": True,
            }
        except OSError as exc:
            return {
                "content": [{"type": "text", "text": f"{name}: çalıştırılamadı — {exc}"}],
                "isError": True,
            }
        text = truncate_output(proc.stdout or "")
        if not text.strip():
            text = f"{name}: çıktı yok (exit {proc.returncode})"
        return {
            "content": [{"type": "text", "text": text}],
            "isError": proc.returncode != 0,
        }

    def handle(self, message: object) -> dict | None:
        """Bir mesajı işler; yanıt yoksa None (bildirimler)."""
        if not isinstance(message, dict):
            return rpc_error(None, INVALID_REQUEST, "geçersiz istek: JSON nesnesi bekleniyor")
        is_notification = "id" not in message
        msg_id = message.get("id")
        method = message.get("method")
        if not isinstance(method, str) or not method:
            if is_notification:
                return None
            return rpc_error(msg_id, INVALID_REQUEST, "geçersiz istek: method yok")
        if method == "notifications/initialized":
            return None
        if method == "tools/call" and is_notification:
            return None
        params = message.get("params", {})
        try:
            if method == "initialize":
                if isinstance(params, dict):
                    result = self.initialize(params)
                else:
                    raise ValueError("params bir nesne olmalı")
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                result = self.call_tool(params)
            else:
                if is_notification:
                    return None
                return rpc_error(msg_id, METHOD_NOT_FOUND, f"bilinmeyen metot: {method}")
        except LookupError as exc:
            return rpc_error(msg_id, INVALID_PARAMS, str(exc))
        except ValueError as exc:
            return rpc_error(msg_id, INVALID_PARAMS, str(exc))
        except Exception as exc:  # süreç düşmez
            return rpc_error(msg_id, INTERNAL_ERROR, f"iç hata: {exc}")
        if is_notification:
            return None
        return rpc_ok(msg_id, result)

    def handle_line(self, line: str) -> dict | None:
        if not line.strip():
            return None
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            return rpc_error(None, PARSE_ERROR, f"bozuk JSON: {exc.msg}")
        return self.handle(message)

    def serve(self, stream_in, stream_out) -> None:
        for raw in stream_in:
            if isinstance(raw, bytes):
                line = raw.decode("utf-8", errors="replace")
            else:
                line = raw
            if len(line) > MAX_LINE:
                response = rpc_error(
                    None, INVALID_REQUEST, f"satır çok uzun (> {MAX_LINE} bayt)"
                )
            else:
                response = self.handle_line(line)
            if response is None:
                continue
            try:
                stream_out.write(json.dumps(response, ensure_ascii=False) + "\n")
                stream_out.flush()
            except (BrokenPipeError, OSError):
                return


def main() -> int:
    parser = argparse.ArgumentParser(
        description="salt-okunur stdio MCP sunucusu (JSON-RPC 2.0)"
    )
    parser.add_argument("--project", type=Path, help="proje kökü (kit.config.yaml)")
    args = parser.parse_args()

    try:
        project = resolve_project(args.project, Path.cwd())
    except ServerError as exc:
        print(f"mcp_server: {exc}", file=sys.stderr)
        return 1

    config = load_config(project)
    kit_root = find_kit_root(project, config)
    if kit_root is None:
        print(
            "mcp_server: uyarı: kit kökü bulunamadı (delivery/scripts/doctor.py|doctor.sh yok)",
            file=sys.stderr,
        )
    server = McpServer(project, kit_root, config)
    server.serve(sys.stdin.buffer, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
