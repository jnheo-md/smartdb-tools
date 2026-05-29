"""
Preprocessing Preference Commands
=================================
Manage optional user-owned preprocessing memory and deterministic profiles.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from smartdb_cli.formatting import console, print_error, print_success, print_warning

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


app = typer.Typer(
    name="preprocess",
    help="Manage optional preprocessing memory and deterministic profiles.",
)
memory_app = typer.Typer(name="memory", help="Manage free-text preprocessing memory.")
app.add_typer(memory_app, name="memory", help="Manage free-text preprocessing memory.")

USER_CONFIG_PATH = Path.home() / ".smartdb" / "preprocess.toml"
USER_MEMORY_PATH = Path.home() / ".smartdb" / "memory" / "preprocess.md"
PROJECT_CONFIG_PATH = Path.cwd() / ".smartdb" / "preprocess.toml"
PROJECT_MEMORY_PATH = Path.cwd() / ".smartdb" / "preprocess.md"

SCOPE_CHOICES = ["user", "project"]
MEMORY_SCOPE_CHOICES = ["combined", "user", "project"]
DISALLOWED_PROFILE_TERMS = (
    "NIHSS_total",
    "admission_mrs_3month",
    "admission_mrs_3month_assume",
    "secret_mrs_3month",
    "mRS 3 month all",
)

STARTER_PROFILE_TOML = """\
# SmartDB optional preprocessing profiles
#
# This file is user-controlled and opt-in. It never changes default SmartDB
# exports unless a user or MCP tool explicitly chooses a profile.
# Free-text preferences belong in ~/.smartdb/memory/preprocess.md.

version = 1

[profile.audit_only]
description = "Do not transform data. Only write an audit summary."
requires_confirmation = true

[profile.audit_only.audit]
enabled = true

# Example legacy-style profile. Keep disabled until reviewed for your project.
[profile.example_evt]
description = "Example EVT export cleanup profile. Review before use."
enabled = false
requires_confirmation = true

[profile.example_evt.dedupe]
enabled = true
mode = "evt"
group_by = ["uniq_id", "thrombolysis_count_during_adm"]
keep = "most_complete"
audit_deleted_rows = true

[[profile.example_evt.derive]]
name = "Reperfusion Tx"
type = "binary_combo_label"
requires_encoding_check = true
sources = { ivt = "Thr_IV", evt = "Thr_mechanical" }
"""

STARTER_MEMORY = """\
# SmartDB Preprocessing Memory

Write user preferences here in plain language. This file is advisory only:
it can guide MCP suggestions, but it cannot directly modify data.

Examples:
- For my EVT exports, identify duplicates by uniq_id + thrombolysis_count_during_adm.
- Keep the most complete row, but always create an audit sheet first.
- Never overwrite the original file.
- Ask before creating derived columns.
"""

BUILTIN_CONFIG: dict[str, Any] = {
    "version": 1,
    "profile": {
        "audit_only": {
            "description": "Built-in safe profile. No transformations; audit only.",
            "requires_confirmation": True,
            "audit": {"enabled": True},
        }
    },
}


def _scope_paths(scope: str) -> tuple[Path, Path]:
    if scope == "user":
        return USER_CONFIG_PATH, USER_MEMORY_PATH
    if scope == "project":
        return PROJECT_CONFIG_PATH, PROJECT_MEMORY_PATH
    print_error(f"Invalid scope '{scope}'. Use: user or project.")
    raise typer.Exit(code=1)


def _load_toml_file(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        print_error(f"Invalid TOML in {path}: {exc}")
        raise typer.Exit(code=1)
    except OSError as exc:
        print_error(f"Could not read {path}: {exc}")
        raise typer.Exit(code=1)


def _profile_sources(config: Path | None = None) -> list[tuple[str, Path | None, dict[str, Any]]]:
    if config:
        return [(f"explicit:{config}", config, _load_toml_file(config))]

    sources: list[tuple[str, Path | None, dict[str, Any]]] = []
    if USER_CONFIG_PATH.exists():
        sources.append(("user", USER_CONFIG_PATH, _load_toml_file(USER_CONFIG_PATH)))
    if PROJECT_CONFIG_PATH.exists():
        sources.append(("project", PROJECT_CONFIG_PATH, _load_toml_file(PROJECT_CONFIG_PATH)))
    sources.append(("built-in", None, BUILTIN_CONFIG))
    return sources


def _collect_profiles(config: Path | None = None) -> dict[str, tuple[str, Path | None, dict[str, Any]]]:
    profiles: dict[str, tuple[str, Path | None, dict[str, Any]]] = {}
    for source_name, source_path, payload in _profile_sources(config):
        source_profiles = payload.get("profile", {})
        if not isinstance(source_profiles, dict):
            continue
        for name, profile in source_profiles.items():
            if name not in profiles and isinstance(profile, dict):
                profiles[name] = (source_name, source_path, profile)
    return profiles


def _profile_as_text(name: str, profile: dict[str, Any]) -> str:
    lines = [name]
    lines.append(f"description: {profile.get('description', '')}")
    for key, value in profile.items():
        if key == "description":
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _validate_profile(name: str, profile: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(profile.get("description", ""), str) or not profile.get("description"):
        issues.append("Missing profile description.")

    serialized = str(profile)
    for term in DISALLOWED_PROFILE_TERMS:
        if term in serialized:
            issues.append(
                f"Profile references '{term}', which is blocked for preprocessing profiles. "
                "Use SmartDB follow-up/NIHSS tools instead."
            )

    dedupe = profile.get("dedupe")
    if dedupe is not None:
        if not isinstance(dedupe, dict):
            issues.append("dedupe must be a table/object.")
        else:
            group_by = dedupe.get("group_by", [])
            if dedupe.get("enabled") and not isinstance(group_by, list):
                issues.append("dedupe.group_by must be a list.")
            if dedupe.get("keep") not in (None, "most_complete", "first", "last"):
                issues.append("dedupe.keep must be one of: most_complete, first, last.")

    derives = profile.get("derive", [])
    if derives is not None:
        if not isinstance(derives, list):
            issues.append("derive must be an array of tables.")
        else:
            for index, rule in enumerate(derives, 1):
                if not isinstance(rule, dict):
                    issues.append(f"derive rule #{index} must be a table/object.")
                    continue
                if not rule.get("name"):
                    issues.append(f"derive rule #{index} is missing name.")
                if not rule.get("type"):
                    issues.append(f"derive rule #{index} is missing type.")

    return issues


def _memory_paths_for_scope(scope: str) -> list[tuple[str, Path]]:
    if scope == "combined":
        return [("user", USER_MEMORY_PATH), ("project", PROJECT_MEMORY_PATH)]
    if scope == "user":
        return [("user", USER_MEMORY_PATH)]
    if scope == "project":
        return [("project", PROJECT_MEMORY_PATH)]
    print_error("Invalid scope. Use: combined, user, or project.")
    raise typer.Exit(code=1)


@app.command("init")
def init(
    scope: str = typer.Option(
        "user",
        "--scope",
        "-s",
        help="Where to create files: user or project.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing starter files."),
) -> None:
    """Create starter preprocessing memory and profile files."""
    if scope not in SCOPE_CHOICES:
        print_error("Invalid scope. Use: user or project.")
        raise typer.Exit(code=1)

    config_path, memory_path = _scope_paths(scope)
    for path, content in ((config_path, STARTER_PROFILE_TOML), (memory_path, STARTER_MEMORY)):
        if path.exists() and not force:
            print_warning(f"Already exists: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print_success(f"Wrote {path}")


@memory_app.command("add")
def memory_add(
    note: str = typer.Argument(..., help="Free-text preprocessing preference to remember."),
    scope: str = typer.Option("user", "--scope", "-s", help="Where to save: user or project."),
) -> None:
    """Append a free-text preprocessing preference note."""
    if scope not in SCOPE_CHOICES:
        print_error("Invalid scope. Use: user or project.")
        raise typer.Exit(code=1)

    _, memory_path = _scope_paths(scope)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with memory_path.open("a", encoding="utf-8") as file:
        if memory_path.stat().st_size == 0:
            file.write("# SmartDB Preprocessing Memory\n\n")
        file.write(f"\n## {timestamp}\n{note.strip()}\n")
    print_success(f"Saved preprocessing memory to {memory_path}")


@memory_app.command("show")
def memory_show(
    scope: str = typer.Option(
        "combined",
        "--scope",
        "-s",
        help="Memory scope to show: combined, user, or project.",
    ),
) -> None:
    """Show free-text preprocessing memory."""
    for source_name, path in _memory_paths_for_scope(scope):
        console.print(f"[bold cyan]{source_name} memory:[/bold cyan] {path}")
        if not path.exists():
            console.print("[dim]No memory file found.[/dim]\n")
            continue
        console.print(Syntax(path.read_text(encoding="utf-8"), "markdown"))


@app.command("list-profiles")
def list_profiles(
    config: Path | None = typer.Option(None, "--config", "-c", help="Explicit TOML profile file."),
) -> None:
    """List available deterministic preprocessing profiles."""
    profiles = _collect_profiles(config)
    table = Table(title="Preprocessing Profiles")
    table.add_column("Profile", style="bold cyan")
    table.add_column("Source")
    table.add_column("Config Path")
    table.add_column("Description")
    for name, (source_name, source_path, profile) in sorted(profiles.items()):
        table.add_row(
            name,
            source_name,
            str(source_path) if source_path else "(built-in)",
            str(profile.get("description", "")),
        )
    console.print(table)


@app.command("explain")
def explain(
    profile_name: str = typer.Argument(..., help="Profile name to explain."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Explicit TOML profile file."),
) -> None:
    """Explain one deterministic preprocessing profile."""
    profiles = _collect_profiles(config)
    if profile_name not in profiles:
        print_error(f"Profile '{profile_name}' was not found.")
        raise typer.Exit(code=1)
    source_name, source_path, profile = profiles[profile_name]
    issues = _validate_profile(profile_name, profile)
    body = [
        f"Source: {source_name}",
        f"Config: {source_path or '(built-in)'}",
        "",
        _profile_as_text(profile_name, profile),
    ]
    if issues:
        body.extend(["", "Validation issues:", *[f"- {issue}" for issue in issues]])
    console.print(Panel("\n".join(body), title=f"Profile: {profile_name}", border_style="cyan"))


@app.command("validate")
def validate(
    profile_name: str | None = typer.Argument(None, help="Optional profile name to validate."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Explicit TOML profile file."),
) -> None:
    """Validate preprocessing profile syntax and safety constraints."""
    profiles = _collect_profiles(config)
    if profile_name:
        profiles = {profile_name: profiles[profile_name]} if profile_name in profiles else {}
    if not profiles:
        print_error("No matching preprocessing profiles found.")
        raise typer.Exit(code=1)

    failed = False
    table = Table(title="Preprocessing Profile Validation")
    table.add_column("Profile", style="bold cyan")
    table.add_column("Status")
    table.add_column("Issues")
    for name, (_, _, profile) in sorted(profiles.items()):
        issues = _validate_profile(name, profile)
        if issues:
            failed = True
            table.add_row(name, "[red]failed[/red]", "\n".join(issues))
        else:
            table.add_row(name, "[green]ok[/green]", "")
    console.print(table)
    if failed:
        raise typer.Exit(code=1)


@app.command("context")
def context() -> None:
    """Show what MCP/AI tools should use as preprocessing context."""
    profiles = _collect_profiles()
    lines = [
        "SmartDB preprocessing context is advisory and opt-in.",
        "Free-text memory can guide suggestions, but deterministic TOML profiles run actual rules.",
        "MCP should ask for confirmation before applying any profile.",
        "",
        "Memory files:",
        f"  user: {USER_MEMORY_PATH}",
        f"  project: {PROJECT_MEMORY_PATH}",
        "",
        "Profile files:",
        f"  user: {USER_CONFIG_PATH}",
        f"  project: {PROJECT_CONFIG_PATH}",
        "",
        "Available profiles:",
    ]
    for name, (source_name, source_path, profile) in sorted(profiles.items()):
        lines.append(f"  - {name} ({source_name}): {profile.get('description', '')}")
        if source_path:
            lines.append(f"    {source_path}")
    console.print(Panel("\n".join(lines), title="Preprocessing Context", border_style="cyan"))
