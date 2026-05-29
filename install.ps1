#Requires -Version 5.1
<#
.SYNOPSIS
    SmartDB Tools Installer for Windows
.DESCRIPTION
    Installs the SmartDB CLI and MCP server into %USERPROFILE%\.smartdb
    Usage:  irm https://raw.githubusercontent.com/jnheo-md/smartdb-tools/master/install.ps1 | iex
#>

$ErrorActionPreference = "Stop"

$INSTALL_DIR = Join-Path $env:USERPROFILE ".smartdb"
$VENV_DIR    = Join-Path $INSTALL_DIR "venv"
$SCRIPTS_DIR = Join-Path $VENV_DIR "Scripts"
$MCP_DIR     = Join-Path $INSTALL_DIR "mcp-server"
$REFERENCE_CACHE_DIR = Join-Path $INSTALL_DIR "reference-cache"
$API_URL     = "https://api.ai.smartstroke.net"
$REPO_URL    = "https://github.com/jnheo-md/smartdb-tools.git"
$MIN_PYTHON  = [version]"3.10"

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Dim   { param($msg) Write-Host "  $msg" -ForegroundColor DarkGray }
function Write-Good  { param($msg) Write-Host "  $msg" -ForegroundColor Green }
function Write-Bad   { param($msg) Write-Host "  $msg" -ForegroundColor Red }
function Write-Bold  { param($msg) Write-Host "  $msg" -ForegroundColor White }

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,

        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Command 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        Write-Bad $ErrorMessage
        if ($output) {
            foreach ($line in $output) {
                Write-Dim $line.ToString()
            }
        }
        exit 1
    }

    return $output
}

function Find-Python {
    # Try versioned names first, then plain python3 / python
    foreach ($name in @("python3", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            $ver = & $cmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -and [version]$ver -ge $MIN_PYTHON) {
                return $cmd.Source
            }
        }
    }
    # Check py launcher (common on Windows)
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
        $ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -and [version]$ver -ge $MIN_PYTHON) {
            return "py -3"
        }
    }
    return $null
}

# ── Main ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Bold "SmartDB Tools Installer (Windows)"
Write-Bold "=================================="
Write-Host ""

# ── 0. Get source files ─────────────────────────────────────────────────────

$sourceDir = $null
$tempClone = $null

# Check if running from inside the repo
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { $null }
if ($scriptDir -and (Test-Path (Join-Path $scriptDir "cli\pyproject.toml"))) {
    $sourceDir = $scriptDir
    Write-Dim "Running from local clone: $sourceDir"
} else {
    # Running via irm | iex — clone to temp
    Write-Dim "Downloading SmartDB Tools..."
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Bad "Error: git is required. Install Git for Windows and try again."
        Write-Bad "Download from: https://git-scm.com/download/win"
        exit 1
    }
    $tempClone = Join-Path $env:TEMP "smartdb-tools-install-$(Get-Random)"
    Invoke-NativeCommand -ErrorMessage "Error: Failed to clone repository." -Command {
        git clone --quiet --depth 1 $REPO_URL $tempClone
    } | Out-Null
    $sourceDir = $tempClone
    Write-Dim "Downloaded to temporary directory."
}

$cliDir = Join-Path $sourceDir "cli"
$mcpSourceDir = Join-Path $sourceDir "mcp-server"

# ── 1. Find Python ──────────────────────────────────────────────────────────

$py = Find-Python
if (-not $py) {
    Write-Bad "Error: Python >= $MIN_PYTHON is required but not found."
    Write-Bad "Install from https://www.python.org/downloads/"
    Write-Bad "IMPORTANT: Check 'Add Python to PATH' during installation."
    exit 1
}

# Handle "py -3" case
$pyArgs = @()
if ($py -eq "py -3") {
    $pyExe = "py"
    $pyArgs = @("-3")
} else {
    $pyExe = $py
}

$pyVer = & $pyExe @pyArgs --version 2>&1
Write-Dim "Using $pyVer ($pyExe $($pyArgs -join ' '))"

# ── 2. Create / reuse venv ──────────────────────────────────────────────────

if (Test-Path $VENV_DIR) {
    Write-Dim "Reusing existing virtualenv at $VENV_DIR"
} else {
    Write-Dim "Creating virtualenv at $VENV_DIR ..."
    New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
    & $pyExe @pyArgs -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Bad "Error: Failed to create virtual environment."
        exit 1
    }
}

$pip = Join-Path $SCRIPTS_DIR "pip.exe"
& $pip install --quiet --upgrade pip 2>$null

# ── 3. Install smartdb-cli ──────────────────────────────────────────────────

if (Test-Path $cliDir) {
    Write-Dim "Installing smartdb-cli from $cliDir ..."
    & $pip install --quiet $cliDir
} else {
    Write-Bad "Error: cli directory not found at $cliDir"
    exit 1
}

$smartdb = Join-Path $SCRIPTS_DIR "smartdb.exe"
if (-not (Test-Path $smartdb)) {
    Write-Bad "Error: smartdb-cli installation failed — smartdb.exe not found."
    exit 1
}
$cliVer = & $smartdb --version 2>&1
Write-Dim "smartdb-cli installed: $cliVer"

# ── 4. Install MCP server dependencies ──────────────────────────────────────

Write-Dim "Installing MCP server dependencies ..."
& $pip install --quiet "mcp[cli]>=1.0.0" "httpx>=0.25.0"

# ── 5. Copy MCP server files ────────────────────────────────────────────────

Write-Dim "Copying MCP server files to $MCP_DIR ..."
New-Item -ItemType Directory -Path $MCP_DIR -Force | Out-Null
foreach ($f in @("server.py", "api_client.py", "variable_safety.py")) {
    $src = Join-Path $mcpSourceDir $f
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $MCP_DIR $f) -Force
    }
}

# ── 5b. Copy generated field reference cache if bundled ────────────────────

$referenceSource = Join-Path $sourceDir "reference\hospital-field-reference\smartdb_field_reference.json"
if (Test-Path $referenceSource) {
    Write-Dim "Copying field reference cache to $REFERENCE_CACHE_DIR ..."
    New-Item -ItemType Directory -Path $REFERENCE_CACHE_DIR -Force | Out-Null
    Copy-Item $referenceSource (Join-Path $REFERENCE_CACHE_DIR "smartdb_field_reference.json") -Force
}

# ── 6. Add to PATH if needed ────────────────────────────────────────────────

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -split ";" | Where-Object { $_ -eq $SCRIPTS_DIR }) {
    Write-Dim "$SCRIPTS_DIR is already in PATH."
} else {
    $newPath = "$userPath;$SCRIPTS_DIR"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:PATH = "$env:PATH;$SCRIPTS_DIR"
    Write-Dim "Added $SCRIPTS_DIR to user PATH."
}

# ── 7. Configure API URL ────────────────────────────────────────────────────

Write-Dim "Setting API URL to $API_URL ..."
& $smartdb config set-url $API_URL

# ── 8. Login ─────────────────────────────────────────────────────────────────

Write-Host ""
Write-Bold "Login to SmartDB"
Write-Host "  Enter your credentials to authenticate with the API server."
Write-Host ""
& $smartdb login
if ($LASTEXITCODE -ne 0) {
    Write-Bad "Login failed after retries. Run 'smartdb login' later to try again."
    exit 1
}

# ── 9. Auto-configure MCP for AI tools ───────────────────────────────────────

Write-Host ""
Write-Bold "MCP Configuration"
Write-Host ""
& $smartdb ai setup --tools auto
if ($LASTEXITCODE -ne 0) {
    Write-Dim "MCP auto-configuration did not complete."
    Write-Dim "Retry later with: smartdb ai setup --tools auto"
}

# ── Cleanup temp clone ───────────────────────────────────────────────────────

if ($tempClone -and (Test-Path $tempClone)) {
    Remove-Item $tempClone -Recurse -Force -ErrorAction SilentlyContinue
}

# ── Done ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Good "SmartDB Tools installed successfully!"
Write-Host ""
Write-Host "  Verify with:"
Write-Host "    smartdb whoami"
Write-Host "    smartdb ai setup --tools auto   # configure/reconfigure AI tools"
Write-Host ""
Write-Host "  MCP server files:  $MCP_DIR\"
Write-Host "  Python venv:       $VENV_DIR\"
Write-Host ""
