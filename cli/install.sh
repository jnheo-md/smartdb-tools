#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.ysr3"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$VENV_DIR/bin"
MIN_PYTHON_MINOR=10
API_URL="https://api.ai.smartstroke.net"

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

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    bold "  YSR3 CLI Installer"
    bold "  ==================="
    echo ""

    local src_dir
    src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

    # ── 3. Install ysr3-cli ──────────────────────────────────────────────────
    dim "  Installing ysr3-cli ..."
    "$BIN_DIR/pip" install --quiet "$src_dir"

    if ! "$BIN_DIR/ysr3" --version &>/dev/null; then
        red "  Error: installation succeeded but ysr3 binary not found."
        exit 1
    fi
    dim "  ysr3-cli installed: $("$BIN_DIR/ysr3" --version 2>&1)"

    # ── 4. Add to PATH if needed ─────────────────────────────────────────────
    local rc_file line_to_add
    rc_file=$(detect_shell_rc)
    line_to_add=$(path_line)

    if echo "$PATH" | tr ':' '\n' | grep -qxF "$BIN_DIR"; then
        dim "  $BIN_DIR is already in PATH."
    elif [ -f "$rc_file" ] && grep -qF "$BIN_DIR" "$rc_file" 2>/dev/null; then
        dim "  PATH entry already in $rc_file (restart your shell to activate)."
    else
        if [ -f "$rc_file" ]; then
            cp "$rc_file" "${rc_file}.bak.$(date +%s)"
            dim "  Backed up $rc_file"
        fi
        echo "" >> "$rc_file"
        echo "# YSR3 CLI (SmartDB Tools)" >> "$rc_file"
        echo "$line_to_add" >> "$rc_file"
        dim "  Added $BIN_DIR to PATH in $rc_file"
    fi

    # ── 5. Configure API URL ─────────────────────────────────────────────────
    dim "  Setting API URL to $API_URL ..."
    "$BIN_DIR/ysr3" config set-url "$API_URL"

    # ── 6. Login (unless --no-login) ─────────────────────────────────────────
    if [ "$NO_LOGIN" = false ]; then
        echo ""
        bold "  Login to YSR3"
        echo "  Enter your credentials to authenticate with the API server."
        echo ""
        "$BIN_DIR/ysr3" login
        echo ""
    else
        dim "  Skipping login (--no-login flag set)."
        echo ""
    fi

    # ── Done ─────────────────────────────────────────────────────────────────
    echo ""
    green "  ✓ ysr3-cli installed successfully!"
    echo ""
    echo "  Verify with:"
    echo "    ysr3 whoami"
    echo ""
    echo "  To install the MCP server for AI tools (Claude, Cursor, etc.),"
    echo "  see: https://github.com/jnheo-md/smartdb-tools"
    echo ""
    if ! echo "$PATH" | tr ':' '\n' | grep -qxF "$BIN_DIR"; then
        dim "  Run 'source $rc_file' or open a new terminal to update PATH."
        echo ""
    fi
}

main "$@"
