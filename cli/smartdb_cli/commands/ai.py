"""
AI Assistant Setup Commands
===========================
Configure the SmartDB MCP server for local AI assistants.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

import typer
from rich.syntax import Syntax
from rich.table import Table

from smartdb_cli.config import MCP_DIR, VENV_DIR
from smartdb_cli.formatting import console, print_error, print_success, print_warning

app = typer.Typer(name="ai", help="Configure SmartDB for AI assistants and MCP clients.")

CONFIGURABLE_TOOLS = (
    "claude-code",
    "claude-desktop",
    "codex",
    "cursor",
    "windsurf",
    "pi-agent",
)

TOOL_ALIASES = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "claude-cli": "claude-code",
    "claude-desktop": "claude-desktop",
    "claude-app": "claude-desktop",
    "desktop": "claude-desktop",
    "codex": "codex",
    "codex-cli": "codex",
    "cursor": "cursor",
    "windsurf": "windsurf",
    "pi": "pi-agent",
    "pi-agent": "pi-agent",
    "pi-coding-agent": "pi-agent",
    "manual": "manual",
}


def _smartdb_python() -> Path:
    executable = "python.exe" if os.name == "nt" else "python"
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    return VENV_DIR / scripts_dir / executable


def _smartdb_server() -> Path:
    return MCP_DIR / "server.py"


def _ensure_mcp_install() -> tuple[str, str]:
    python_path = _smartdb_python()
    server_path = _smartdb_server()
    missing = [path for path in (python_path, server_path) if not path.exists()]
    if missing:
        missing_lines = "\n".join(f"  - {path}" for path in missing)
        print_error(
            "SmartDB MCP files are missing. Run the SmartDB installer first.\n"
            f"{missing_lines}"
        )
        raise typer.Exit(code=1)
    return str(python_path), str(server_path)


def _normalize_tool_name(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    return TOOL_ALIASES.get(normalized, normalized)


def _parse_tools(tools: str) -> list[str]:
    parsed: list[str] = []
    for raw_value in re.split(r"[,;]", tools):
        value = _normalize_tool_name(raw_value)
        if not value:
            continue
        if value == "all":
            return list(CONFIGURABLE_TOOLS)
        if value == "auto":
            return ["auto"]
        if value not in CONFIGURABLE_TOOLS and value != "manual":
            print_error(
                f"Unknown AI tool '{raw_value.strip()}'. Use one of: "
                "auto, all, claude-code, claude-desktop, codex, cursor, "
                "windsurf, pi-agent, manual."
            )
            raise typer.Exit(code=1)
        if value not in parsed:
            parsed.append(value)
    return parsed or ["auto"]


def _detect_tools() -> list[str]:
    detected: list[str] = []

    if shutil.which("claude"):
        detected.append("claude-code")

    if _is_claude_desktop_detected():
        detected.append("claude-desktop")

    if _is_path_or_command_detected(Path.home() / ".codex", "codex"):
        detected.append("codex")

    if _is_path_or_command_detected(Path.home() / ".cursor", "cursor"):
        detected.append("cursor")

    if _is_path_or_command_detected(Path.home() / ".codeium" / "windsurf", "windsurf"):
        detected.append("windsurf")

    if (Path.home() / ".pi" / "agent").exists():
        detected.append("pi-agent")

    return detected


def _is_path_or_command_detected(path: Path, command: str) -> bool:
    return path.exists() or shutil.which(command) is not None


def _is_claude_desktop_detected() -> bool:
    system = platform.system()
    if system == "Darwin":
        return (
            Path("/Applications/Claude.app").exists()
            or (Path.home() / "Library" / "Application Support" / "Claude").exists()
        )
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        return bool(appdata and (Path(appdata) / "Claude").exists())
    return (Path.home() / ".config" / "Claude").exists()


def _confirm(tool_label: str, yes: bool) -> bool:
    if yes:
        return True
    try:
        return typer.confirm(f"Configure SmartDB MCP for {tool_label}?", default=True)
    except (EOFError, KeyboardInterrupt):
        return False


def _load_json_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        backup_path = config_path.with_name(f"{config_path.name}.bak")
        shutil.copy2(config_path, backup_path)
        print_warning(
            f"Existing config was invalid JSON. Backed it up to {backup_path} "
            "and wrote a new config."
        )
        return {}


def _merge_mcp_json_config(config_path: Path, python_path: str, server_path: str) -> None:
    data = _load_json_config(config_path)
    mcp_servers = data.setdefault("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        data["mcpServers"] = {}

    data["mcpServers"]["smartdb"] = {
        "command": python_path,
        "args": [server_path],
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _replace_toml_table(text: str, table_name: str, replacement: str) -> str:
    lines = text.splitlines()
    table_header = re.compile(rf"^\s*\[{re.escape(table_name)}\]\s*(?:#.*)?$")
    any_header = re.compile(r"^\s*\[[^\]]+\]\s*(?:#.*)?$")
    target_or_nested_header = re.compile(
        rf"^\s*\[{re.escape(table_name)}(?:\]|\.)"
    )
    output: list[str] = []
    index = 0
    replaced = False

    while index < len(lines):
        if table_header.match(lines[index]):
            output.extend(replacement.strip().splitlines())
            replaced = True
            index += 1
            while index < len(lines):
                if any_header.match(lines[index]) and not target_or_nested_header.match(lines[index]):
                    break
                index += 1
            continue

        output.append(lines[index])
        index += 1

    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.extend(replacement.strip().splitlines())

    return "\n".join(output).rstrip() + "\n"


def _write_codex_config(config_path: Path, python_path: str, server_path: str) -> None:
    block = (
        "[mcp_servers.smartdb]\n"
        f"command = {json.dumps(python_path)}\n"
        f"args = [{json.dumps(server_path)}]\n"
    )
    current = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    updated = _replace_toml_table(current, "mcp_servers.smartdb", block)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(updated, encoding="utf-8")


def _claude_desktop_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _remove_stale_claude_settings() -> None:
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        return

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    mcp_servers = data.get("mcpServers")
    if not isinstance(mcp_servers, dict):
        return

    changed = False
    for stale_name in ("smartdb", "ysr3"):
        if stale_name in mcp_servers:
            mcp_servers.pop(stale_name, None)
            changed = True

    if changed:
        if not mcp_servers:
            data.pop("mcpServers", None)
        settings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _configure_claude_code(python_path: str, server_path: str) -> bool:
    if not shutil.which("claude"):
        print_warning("Claude Code CLI was not found. Install Claude Code, then rerun this command.")
        return False

    _remove_stale_claude_settings()
    result = subprocess.run(
        [
            "claude",
            "mcp",
            "add",
            "--scope",
            "user",
            "--transport",
            "stdio",
            "smartdb",
            "--",
            python_path,
            server_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_error(f"Claude Code setup failed: {result.stderr.strip() or result.stdout.strip()}")
        return False

    print_success("Claude Code configured (user scope).")
    return True


def _configure_claude_desktop(python_path: str, server_path: str) -> bool:
    config_path = _claude_desktop_config_path()
    _merge_mcp_json_config(config_path, python_path, server_path)
    print_success(f"Claude Desktop configured: {config_path}")
    return True


def _configure_codex(python_path: str, server_path: str) -> bool:
    config_path = Path.home() / ".codex" / "config.toml"
    _write_codex_config(config_path, python_path, server_path)
    print_success(f"Codex configured: {config_path}")
    return True


def _configure_cursor(python_path: str, server_path: str) -> bool:
    config_path = Path.home() / ".cursor" / "mcp.json"
    _merge_mcp_json_config(config_path, python_path, server_path)
    print_success(f"Cursor configured: {config_path}")
    return True


def _configure_windsurf(python_path: str, server_path: str) -> bool:
    config_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    _merge_mcp_json_config(config_path, python_path, server_path)
    print_success(f"Windsurf configured: {config_path}")
    return True


def _configure_pi_agent(python_path: str, server_path: str) -> bool:
    config_path = Path.home() / ".pi" / "agent" / "mcp.json"
    _merge_mcp_json_config(config_path, python_path, server_path)
    print_success(f"Pi Coding Agent configured: {config_path}")
    return True


def _print_manual_config(python_path: str, server_path: str) -> None:
    json_config = {
        "mcpServers": {
            "smartdb": {
                "command": python_path,
                "args": [server_path],
            }
        }
    }
    codex_config = (
        "[mcp_servers.smartdb]\n"
        f"command = {json.dumps(python_path)}\n"
        f"args = [{json.dumps(server_path)}]\n"
    )

    console.print("\n[bold]Generic MCP JSON[/bold]")
    console.print(Syntax(json.dumps(json_config, ensure_ascii=False, indent=2), "json"))
    console.print("[bold]Codex TOML[/bold]")
    console.print(Syntax(codex_config, "toml"))


def _print_detected_tools(tools: list[str]) -> None:
    if not tools:
        return

    table = Table(title="Detected AI Tools", show_header=True)
    table.add_column("Tool", style="bold cyan")
    table.add_column("Action")
    for tool in tools:
        table.add_row(tool, "configure SmartDB MCP")
    console.print(table)


def _run_setup(tools: str, yes: bool) -> None:
    python_path, server_path = _ensure_mcp_install()
    selected_tools = _parse_tools(tools)

    if selected_tools == ["auto"]:
        selected_tools = _detect_tools()
        if not selected_tools:
            print_warning("No supported AI tools were detected.")
            _print_manual_config(python_path, server_path)
            return
        _print_detected_tools(selected_tools)

    handlers = {
        "claude-code": ("Claude Code", _configure_claude_code),
        "claude-desktop": ("Claude Desktop", _configure_claude_desktop),
        "codex": ("Codex", _configure_codex),
        "cursor": ("Cursor", _configure_cursor),
        "windsurf": ("Windsurf", _configure_windsurf),
        "pi-agent": ("Pi Coding Agent", _configure_pi_agent),
    }

    successes = 0
    failures = 0

    for tool in selected_tools:
        if tool == "manual":
            _print_manual_config(python_path, server_path)
            continue

        label, handler = handlers[tool]
        if not _confirm(label, yes):
            console.print(f"[dim]Skipped {label}.[/dim]")
            continue

        if handler(python_path, server_path):
            successes += 1
        else:
            failures += 1

    if successes:
        console.print("\n[dim]Restart the configured AI app so it reloads MCP settings.[/dim]")
    elif failures:
        raise typer.Exit(code=1)


@app.command("setup")
def setup(
    tools: str = typer.Option(
        "auto",
        "--tools",
        "-t",
        help=(
            "Comma-separated tools: auto, all, claude-code, claude-desktop, "
            "codex, cursor, windsurf, pi-agent, manual."
        ),
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Configure selected tools without prompts."),
) -> None:
    """Configure SmartDB MCP for AI assistants."""
    _run_setup(tools, yes)


@app.command("install")
def install(
    tools: str = typer.Option(
        "auto",
        "--tools",
        "-t",
        help=(
            "Comma-separated tools: auto, all, claude-code, claude-desktop, "
            "codex, cursor, windsurf, pi-agent, manual."
        ),
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Configure selected tools without prompts."),
) -> None:
    """Alias for 'smartdb ai setup'."""
    _run_setup(tools, yes)
