#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.smartdb"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$VENV_DIR/bin"
MCP_DIR="$INSTALL_DIR/mcp-server"

# ── Colours ──────────────────────────────────────────────────────────────────
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

# ── Merge MCP config into a JSON file using Python ─────────────────────────
merge_mcp_config() {
    local config_file="$1"
    local python_cmd="$2"
    local server_script="$3"

    "$python_cmd" - "$config_file" "$python_cmd" "$server_script" <<'PYEOF'
import json, sys, os

config_file = sys.argv[1]
python_path = sys.argv[2]
server_script = sys.argv[3]

data = {}
if os.path.isfile(config_file):
    try:
        with open(config_file, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        data = {}

if "mcpServers" not in data:
    data["mcpServers"] = {}

data["mcpServers"]["smartdb"] = {
    "command": python_path,
    "args": [server_script],
}

os.makedirs(os.path.dirname(config_file), exist_ok=True)
with open(config_file, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    bold "  SmartDB MCP Server Installer"
    bold "  ============================"
    echo ""

    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # ── 1. Check that smartdb-cli is already installed ────────────────────────
    if [ ! -d "$VENV_DIR" ] || [ ! -x "$BIN_DIR/smartdb" ]; then
        red "  Error: smartdb-cli is not installed."
        echo ""
        echo "  The MCP server requires the smartdb-cli for authentication."
        echo "  Install it first:"
        echo ""
        echo "    cd /path/to/smartdb-cli && bash install.sh"
        echo ""
        echo "  Or install everything at once from the smartdb-tools repo:"
        echo "    https://github.com/jnheo-md/smartdb-tools"
        echo ""
        exit 1
    fi

    dim "  Found smartdb-cli: $("$BIN_DIR/smartdb" --version 2>&1)"

    # ── 2. Check login status ────────────────────────────────────────────────
    local session_file="$INSTALL_DIR/session.json"
    if [ ! -f "$session_file" ]; then
        echo ""
        bold "  Not logged in"
        echo "  The MCP server needs an active session. Logging in now..."
        echo ""
        "$BIN_DIR/smartdb" login
        echo ""
    else
        dim "  Session file found."
    fi

    # ── 3. Install MCP server dependencies ───────────────────────────────────
    dim "  Installing MCP server dependencies ..."
    "$BIN_DIR/pip" install --quiet "mcp[cli]>=1.0.0" "httpx>=0.25.0"

    # ── 4. Copy MCP server files ─────────────────────────────────────────────
    dim "  Copying MCP server files to $MCP_DIR ..."
    mkdir -p "$MCP_DIR"
    cp "$script_dir/server.py" "$MCP_DIR/server.py"
    cp "$script_dir/api_client.py" "$MCP_DIR/api_client.py"

    # ── 5. Auto-configure MCP for AI tools ───────────────────────────────────
    local venv_python="$BIN_DIR/python"
    local server_script="$MCP_DIR/server.py"
    local configured_any=false

    echo ""
    bold "  MCP Configuration"
    echo ""

    # --- Claude Code ---
    local claude_code_config="$HOME/.claude/settings.json"
    if command -v claude &>/dev/null; then
        read -rp "  Configure MCP for Claude Code? [Y/n] " ans
        ans="${ans:-Y}"
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            merge_mcp_config "$claude_code_config" "$venv_python" "$server_script"
            green "  ✓ Claude Code configured ($claude_code_config)"
            configured_any=true
        fi
    fi

    # --- Claude Desktop (macOS) ---
    local claude_desktop_config="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    if [[ "$(uname)" == "Darwin" ]] && [ -d "/Applications/Claude.app" ]; then
        read -rp "  Configure MCP for Claude Desktop? [Y/n] " ans
        ans="${ans:-Y}"
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            merge_mcp_config "$claude_desktop_config" "$venv_python" "$server_script"
            green "  ✓ Claude Desktop configured ($claude_desktop_config)"
            configured_any=true
        fi
    fi

    # --- Cursor ---
    local cursor_config="$HOME/.cursor/mcp.json"
    if [ -d "$HOME/.cursor" ] || command -v cursor &>/dev/null; then
        read -rp "  Configure MCP for Cursor? [Y/n] " ans
        ans="${ans:-Y}"
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            merge_mcp_config "$cursor_config" "$venv_python" "$server_script"
            green "  ✓ Cursor configured ($cursor_config)"
            configured_any=true
        fi
    fi

    if [ "$configured_any" = false ]; then
        dim "  No AI tools detected. You can manually add this MCP config:"
        echo ""
        echo "    {\"smartdb\": {\"command\": \"$venv_python\", \"args\": [\"$server_script\"]}}"
        echo ""
    fi

    # ── Done ─────────────────────────────────────────────────────────────────
    echo ""
    green "  ✓ SmartDB MCP Server installed successfully!"
    echo ""
    echo "  MCP server files:  $MCP_DIR/"
    echo "  Python venv:       $VENV_DIR/"
    echo ""
}

main "$@"
