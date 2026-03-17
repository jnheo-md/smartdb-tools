#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.smartdb"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$VENV_DIR/bin"
MCP_DIR="$INSTALL_DIR/mcp-server"
MIN_PYTHON_MINOR=10
API_URL="https://api.ai.smartstroke.net"
REPO_URL="https://github.com/jnheo-md/smartdb-tools.git"

NO_LOGIN=false
for arg in "$@"; do
    case "$arg" in
        --no-login) NO_LOGIN=true ;;
    esac
done

# ── Colours ──────────────────────────────────────────────────────────────────
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

# ── Find a suitable Python (>=3.10) ─────────────────────────────────────────
find_python() {
    for minor in 13 12 11 10; do
        for candidate in "python3.${minor}" "python3${minor}"; do
            if command -v "$candidate" &>/dev/null; then
                echo "$candidate"
                return
            fi
        done
    done

    if command -v python3 &>/dev/null; then
        local ver
        ver=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
        if [ "$ver" -ge "$MIN_PYTHON_MINOR" ]; then
            echo "python3"
            return
        fi
    fi

    return 1
}

# ── Detect shell config file ────────────────────────────────────────────────
detect_shell_rc() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")

    case "$shell_name" in
        zsh)  echo "$HOME/.zshrc" ;;
        bash)
            if [[ "$(uname)" == "Darwin" ]]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
            ;;
        fish) echo "$HOME/.config/fish/config.fish" ;;
        *)    echo "$HOME/.profile" ;;
    esac
}

# ── PATH export line for the detected shell ─────────────────────────────────
path_line() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")

    if [[ "$shell_name" == "fish" ]]; then
        echo "fish_add_path $BIN_DIR"
    else
        echo "export PATH=\"$BIN_DIR:\$PATH\""
    fi
}

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
    bold "  SmartDB Tools Installer"
    bold "  ========================"
    echo ""

    # ── 0. Get source files (clone if running via curl | bash) ───────────────
    local source_dir=""

    # Check if we're running from inside the repo
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-}")" 2>/dev/null && pwd)" || script_dir=""

    if [ -n "$script_dir" ] && [ -f "$script_dir/cli/pyproject.toml" ]; then
        source_dir="$script_dir"
        dim "  Running from local clone: $source_dir"
    else
        # Running via curl | bash — clone to temp dir
        dim "  Downloading SmartDB Tools..."
        local tmp_dir
        tmp_dir=$(mktemp -d)
        trap 'rm -rf "$tmp_dir"' EXIT

        if command -v git &>/dev/null; then
            git clone --depth 1 "$REPO_URL" "$tmp_dir/smartdb-tools" 2>/dev/null
            source_dir="$tmp_dir/smartdb-tools"
        else
            red "  Error: git is required. Install git and try again."
            exit 1
        fi
        dim "  Downloaded to temporary directory."
    fi

    local cli_dir="$source_dir/cli"
    local mcp_source_dir="$source_dir/mcp-server"

    # ── 1. Find Python ───────────────────────────────────────────────────────
    local py
    if ! py=$(find_python); then
        red "  Error: Python >= 3.$MIN_PYTHON_MINOR is required but not found."
        red "  Install it from https://www.python.org/downloads/ and try again."
        exit 1
    fi
    local py_ver
    py_ver=$("$py" --version 2>&1)
    dim "  Using $py_ver ($py)"

    # ── 2. Create / reuse venv ───────────────────────────────────────────────
    if [ -d "$VENV_DIR" ]; then
        dim "  Reusing existing virtualenv at $VENV_DIR"
    else
        dim "  Creating virtualenv at $VENV_DIR ..."
        mkdir -p "$INSTALL_DIR"
        "$py" -m venv "$VENV_DIR"
    fi

    "$BIN_DIR/pip" install --quiet --upgrade pip 2>/dev/null

    # ── 3. Install smartdb-cli ────────────────────────────────────────────────
    if [ -d "$cli_dir" ]; then
        dim "  Installing smartdb-cli from $cli_dir ..."
        "$BIN_DIR/pip" install --quiet "$cli_dir"
    else
        red "  Error: cli directory not found at $cli_dir"
        exit 1
    fi

    if ! "$BIN_DIR/smartdb" --version &>/dev/null; then
        red "  Error: smartdb-cli installation failed — smartdb binary not found."
        exit 1
    fi
    dim "  smartdb-cli installed: $("$BIN_DIR/smartdb" --version 2>&1)"

    # ── 4. Install MCP server dependencies ───────────────────────────────────
    dim "  Installing MCP server dependencies ..."
    "$BIN_DIR/pip" install --quiet "mcp[cli]>=1.0.0" "httpx>=0.25.0"

    # ── 5. Copy MCP server files ─────────────────────────────────────────────
    dim "  Copying MCP server files to $MCP_DIR ..."
    mkdir -p "$MCP_DIR"
    cp "$mcp_source_dir/server.py" "$MCP_DIR/server.py"
    cp "$mcp_source_dir/api_client.py" "$MCP_DIR/api_client.py"

    # ── 6. Add to PATH if needed ─────────────────────────────────────────────
    local rc_file line_to_add
    rc_file=$(detect_shell_rc)
    line_to_add=$(path_line)

    if echo "$PATH" | tr ':' '\n' | grep -qxF "$BIN_DIR"; then
        dim "  $BIN_DIR is already in PATH."
    elif [ -f "$rc_file" ] && grep -qF "$BIN_DIR" "$rc_file" 2>/dev/null; then
        dim "  PATH entry already in $rc_file (restart your shell to activate)."
    else
        # Backup shell RC before modifying
        if [ -f "$rc_file" ]; then
            cp "$rc_file" "${rc_file}.bak.$(date +%s)"
            dim "  Backed up $rc_file"
        fi
        echo "" >> "$rc_file"
        echo "# SmartDB CLI (SmartDB Tools)" >> "$rc_file"
        echo "$line_to_add" >> "$rc_file"
        dim "  Added $BIN_DIR to PATH in $rc_file"
    fi

    # ── 7. Configure API URL ─────────────────────────────────────────────────
    dim "  Setting API URL to $API_URL ..."
    "$BIN_DIR/smartdb" config set-url "$API_URL"

    # ── 8. Login (unless --no-login) ─────────────────────────────────────────
    if [ "$NO_LOGIN" = false ]; then
        echo ""
        bold "  Login to SmartDB"
        echo "  Enter your credentials to authenticate with the API server."
        echo ""
        "$BIN_DIR/smartdb" login </dev/tty
        echo ""
    else
        dim "  Skipping login (--no-login flag set)."
        echo ""
    fi

    # ── 9. Auto-configure MCP for AI tools ───────────────────────────────────
    local venv_python="$BIN_DIR/python"
    local server_script="$MCP_DIR/server.py"
    local configured_any=false

    bold "  MCP Configuration"
    echo ""

    # --- Claude Code ---
    local claude_code_config="$HOME/.claude/settings.json"
    if command -v claude &>/dev/null; then
        read -rp "  Configure MCP for Claude Code? [Y/n] " ans </dev/tty
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
        read -rp "  Configure MCP for Claude Desktop? [Y/n] " ans </dev/tty
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
        read -rp "  Configure MCP for Cursor? [Y/n] " ans </dev/tty
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
    green "  ✓ SmartDB Tools installed successfully!"
    echo ""
    echo "  Verify with:"
    echo "    smartdb whoami"
    echo ""
    echo "  MCP server files:  $MCP_DIR/"
    echo "  Python venv:       $VENV_DIR/"
    echo ""
    if ! echo "$PATH" | tr ':' '\n' | grep -qxF "$BIN_DIR"; then
        dim "  Run 'source $rc_file' or open a new terminal to update PATH."
        echo ""
    fi
}

main "$@"
