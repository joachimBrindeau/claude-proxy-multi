# Claude Code Proxy - Chocolatey Install Script

$ErrorActionPreference = 'Stop'

$packageName = 'claude-code-proxy'
$packageVersion = '0.1.0'
$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"

Write-Host "Installing $packageName $packageVersion..." -ForegroundColor Cyan

# ============================================================================
# Step 1: Install Python Package from PyPI
# ============================================================================

Write-Host "Installing Python package from PyPI..." -ForegroundColor Green

try {
    # Install package using pip
    # Use --user flag to avoid permission issues
    & python -m pip install --user "claude-code-proxy==$packageVersion" --no-warn-script-location

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python package"
    }

    Write-Host "✓ Python package installed successfully" -ForegroundColor Green
}
catch {
    Write-Error "Failed to install Python package: $_"
    throw
}

# ============================================================================
# Step 2: Create Data Directory
# ============================================================================

Write-Host "Creating data directory..." -ForegroundColor Green

$dataDir = Join-Path $env:APPDATA "claude-code-proxy\data"

try {
    if (-not (Test-Path $dataDir)) {
        New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
        Write-Host "✓ Created data directory: $dataDir" -ForegroundColor Green
    }
    else {
        Write-Host "✓ Data directory already exists: $dataDir" -ForegroundColor Yellow
    }
}
catch {
    Write-Error "Failed to create data directory: $_"
    throw
}

# ============================================================================
# Step 3: Locate Installed Executable
# ============================================================================

Write-Host "Locating installed executable..." -ForegroundColor Green

# Python user scripts directory (where pip installs executables with --user)
$pythonScriptsDir = Join-Path $env:APPDATA "Python\Python311\Scripts"
$exePath = Join-Path $pythonScriptsDir "claude-code-proxy-api.exe"

# Check if executable exists
if (-not (Test-Path $exePath)) {
    # Try alternative location (system-wide installation)
    $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($pythonPath) {
        $pythonDir = Split-Path -Parent $pythonPath
        $alternativeExePath = Join-Path $pythonDir "Scripts\claude-code-proxy-api.exe"

        if (Test-Path $alternativeExePath) {
            $exePath = $alternativeExePath
        }
        else {
            Write-Error "Could not find claude-code-proxy-api.exe in expected locations"
            throw "Executable not found"
        }
    }
    else {
        Write-Error "Python not found in PATH"
        throw "Python installation not detected"
    }
}

Write-Host "✓ Found executable: $exePath" -ForegroundColor Green

# ============================================================================
# Step 4: Register Windows Service
# ============================================================================

Write-Host "Registering Windows Service..." -ForegroundColor Green

$serviceName = "claude-code-proxy"
$displayName = "Claude Code Proxy"
$description = "Multi-account Claude Code proxy server with automatic rotation"

# Check if service already exists
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

if ($existingService) {
    Write-Host "Service already exists. Stopping and removing..." -ForegroundColor Yellow

    try {
        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
        & sc.exe delete $serviceName
        Start-Sleep -Seconds 2
    }
    catch {
        Write-Warning "Failed to remove existing service: $_"
    }
}

try {
    # Service command arguments
    $serviceArgs = "--host 0.0.0.0 --port 8000"

    # Create service using New-Service cmdlet
    New-Service `
        -Name $serviceName `
        -BinaryPathName "`"$exePath`" $serviceArgs" `
        -DisplayName $displayName `
        -Description $description `
        -StartupType Manual `
        -ErrorAction Stop | Out-Null

    Write-Host "✓ Windows Service registered successfully" -ForegroundColor Green
    Write-Host "  Service Name: $serviceName" -ForegroundColor Cyan
    Write-Host "  Display Name: $displayName" -ForegroundColor Cyan
    Write-Host "  Startup Type: Manual" -ForegroundColor Cyan
}
catch {
    Write-Error "Failed to register Windows Service: $_"
    Write-Warning "You may need to run this installation as Administrator"
    throw
}

# ============================================================================
# Step 5: Configure Service Environment
# ============================================================================

Write-Host "Configuring service environment..." -ForegroundColor Green

try {
    # Set service to run as LocalSystem
    # This ensures the service has access to network and filesystem
    & sc.exe config $serviceName obj= "LocalSystem"

    # Set service recovery options (restart on failure)
    & sc.exe failure $serviceName reset= 86400 actions= restart/60000/restart/60000/restart/60000

    Write-Host "✓ Service environment configured" -ForegroundColor Green
}
catch {
    Write-Warning "Failed to configure service environment: $_"
}

# ============================================================================
# Installation Complete
# ============================================================================

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          Claude Code Proxy Installed! 🎉                 ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Start the service:" -ForegroundColor White
Write-Host "     Start-Service $serviceName" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Add your Claude accounts:" -ForegroundColor White
Write-Host "     http://localhost:8000/accounts" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Use the proxy API:" -ForegroundColor White
Write-Host "     http://localhost:8000/api/v1/messages" -ForegroundColor Yellow
Write-Host ""
Write-Host "Service Management:" -ForegroundColor Cyan
Write-Host "  Start:   Start-Service $serviceName" -ForegroundColor White
Write-Host "  Stop:    Stop-Service $serviceName" -ForegroundColor White
Write-Host "  Restart: Restart-Service $serviceName" -ForegroundColor White
Write-Host "  Status:  Get-Service $serviceName" -ForegroundColor White
Write-Host ""
Write-Host "Data Directory: $dataDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Documentation: https://github.com/joachimbrindeau/claude-proxy-multi" -ForegroundColor Cyan
Write-Host ""
