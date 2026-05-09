# setup_bi.ps1 - One-time setup script for MetaGPT-BI on Windows
# Run from the repo root in PowerShell:
#   .\setup_bi.ps1
#
# What this does:
#   1. Checks Python 3.11+
#   2. Creates a virtual environment in venv/ (if it does not exist)
#   3. Activates the virtual environment
#   4. Installs the MetaGPT-BI package in editable mode (pip install -e .)
#   5. Installs all BI-specific packages
#   6. Registers the `metagpt-bi` console script
#   7. Creates workspace/data/ for your CSV source files
#   8. Copies the LLM config template (config/config2.yaml.example → config/config2.yaml)
#   9. Verifies all key imports

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host "  MetaGPT-BI Setup"
Write-Host "============================================================"
Write-Host ""

# ------------------------------------------------------------------
# 1. Python version check
# ------------------------------------------------------------------
Write-Host "[1/8] Checking Python version..."
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Install Python 3.11 or 3.12 from python.org" -ForegroundColor Red
    exit 1
}
Write-Host "      Found: $pythonVersion"
$versionParts = ($pythonVersion -replace "Python ", "").Split(".")
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
    Write-Host "ERROR: Python 3.11 or 3.12 required (found $pythonVersion)" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# 2. Create virtual environment
# ------------------------------------------------------------------
Write-Host "[2/8] Setting up virtual environment..."
if (-not (Test-Path "venv")) {
    Write-Host "      Creating venv/..."
    python -m venv venv
} else {
    Write-Host "      venv/ already exists, skipping creation."
}

# ------------------------------------------------------------------
# 3. Activate virtual environment
# ------------------------------------------------------------------
Write-Host "[3/8] Activating virtual environment..."
$activateScript = "venv\Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Host "ERROR: Cannot find $activateScript" -ForegroundColor Red
    exit 1
}
& $activateScript
Write-Host "      Virtual environment active."

# ------------------------------------------------------------------
# 4. Install MetaGPT-BI in editable mode
# ------------------------------------------------------------------
Write-Host "[4/8] Installing MetaGPT-BI (editable mode - registers metagpt-bi command)..."
pip install -e . --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install -e . failed" -ForegroundColor Red
    exit 1
}
Write-Host "      Done."

# ------------------------------------------------------------------
# 5. Install BI-specific packages
# ------------------------------------------------------------------
Write-Host "[5/8] Installing BI-specific packages..."
$biPackages = @(
    "duckdb==1.5.2",
    "dbt-core",
    "dbt-duckdb",
    "dbt-postgres",
    "supabase",
    "psycopg2-binary",
    "pandas",
    "openpyxl"
)
foreach ($pkg in $biPackages) {
    Write-Host "      Installing $pkg..."
    pip install $pkg --quiet
}

# airbyte-api may be removed by pip during dbt-postgres install (protobuf conflict) - always reinstall last
Write-Host "      Installing airbyte-api==0.53.0 (pinned - protobuf conflict workaround)..."
pip install "airbyte-api==0.53.0" --quiet

Write-Host "      All BI packages installed."

# ------------------------------------------------------------------
# 6. Verify metagpt-bi command registered
# ------------------------------------------------------------------
Write-Host "[6/8] Verifying metagpt-bi command registration..."
$cmdPath = Get-Command metagpt-bi -ErrorAction SilentlyContinue
if ($cmdPath) {
    Write-Host "      metagpt-bi found at: $($cmdPath.Source)"
} else {
    Write-Host "WARNING: metagpt-bi not found in PATH. Try reopening PowerShell after setup." -ForegroundColor Yellow
}

# ------------------------------------------------------------------
# 7. Create workspace/data/ directory
# ------------------------------------------------------------------
Write-Host "[7/8] Creating workspace/data/ directory for source files..."
New-Item -ItemType Directory -Force -Path "workspace\data" | Out-Null
Write-Host "      workspace\data\ is ready. Place your CSV/Excel files there."

# ------------------------------------------------------------------
# 8. LLM config
# ------------------------------------------------------------------
Write-Host "[8/8] Checking LLM configuration..."
if (-not (Test-Path "config\config2.yaml")) {
    if (Test-Path "config\config2.yaml.example") {
        Copy-Item "config\config2.yaml.example" "config\config2.yaml"
        Write-Host "      Copied config2.yaml.example → config2.yaml" -ForegroundColor Yellow
        Write-Host "      ACTION REQUIRED: Edit config\config2.yaml and add your LLM API key." -ForegroundColor Yellow
    } else {
        Write-Host "      WARNING: config\config2.yaml not found. Create it before running metagpt-bi." -ForegroundColor Yellow
    }
} else {
    Write-Host "      config\config2.yaml already exists."
}

# ------------------------------------------------------------------
# Import verification
# ------------------------------------------------------------------
Write-Host ""
Write-Host "Verifying key imports..."
$imports = @(
    "import duckdb; print('  duckdb OK')",
    "import psycopg2; print('  psycopg2 OK')",
    "import supabase; print('  supabase OK')",
    "import airbyte_api; print('  airbyte_api OK')",
    "import dbt.version; print('  dbt-core OK')",
    "from metagpt.roles.bi.bi_requirements_analyst import BIRequirementsAnalyst; print('  BIRequirementsAnalyst OK')",
    "from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer; print('  BIAnalyticsEngineer OK')",
    "from metagpt.roles.bi.bi_qa_engineer import BIQAEngineer; print('  BIQAEngineer OK')"
)
foreach ($imp in $imports) {
    python -c $imp
}

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "  Setup complete!"
Write-Host ""
Write-Host "  Next steps:"
Write-Host "  1. Edit config\config2.yaml and set your LLM API key"
Write-Host "  2. Place CSV source files in workspace\data\"
Write-Host "  3. Activate the venv in future sessions:"
Write-Host "       .\venv\Scripts\Activate.ps1"
Write-Host "  4. Run your first BI pipeline:"
Write-Host "       metagpt-bi `"I need a sales BI dashboard. I have CSV files.`""
Write-Host ""
Write-Host "  Run 'metagpt-bi --help' for all options."
Write-Host "============================================================"
Write-Host ""
