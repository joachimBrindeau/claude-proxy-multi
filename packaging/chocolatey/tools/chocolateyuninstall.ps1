# Claude Code Proxy - Chocolatey Uninstall Script

$ErrorActionPreference = 'Stop'

$packageName = 'claude-code-proxy'
$serviceName = 'claude-code-proxy'

Write-Host "Uninstalling $packageName..." -ForegroundColor Cyan

# ============================================================================
# Step 1: Stop and Remove Windows Service
# ============================================================================

Write-Host "Removing Windows Service..." -ForegroundColor Green

try {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

    if ($service) {
        # Stop service if running
        if ($service.Status -eq 'Running') {
            Write-Host "Stopping service..." -ForegroundColor Yellow
            Stop-Service -Name $serviceName -Force -ErrorAction Stop
            Write-Host "✓ Service stopped" -ForegroundColor Green
        }

        # Remove service
        Write-Host "Removing service..." -ForegroundColor Yellow
        & sc.exe delete $serviceName

        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Windows Service removed successfully" -ForegroundColor Green
        }
        else {
            Write-Warning "Failed to remove service (exit code: $LASTEXITCODE)"
        }

        # Wait for service to be fully removed
        Start-Sleep -Seconds 2
    }
    else {
        Write-Host "Service not found (already removed)" -ForegroundColor Yellow
    }
}
catch {
    Write-Warning "Error removing Windows Service: $_"
}

# ============================================================================
# Step 2: Uninstall Python Package
# ============================================================================

Write-Host "Uninstalling Python package..." -ForegroundColor Green

try {
    # Uninstall package using pip
    & python -m pip uninstall -y claude-code-proxy

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Python package uninstalled successfully" -ForegroundColor Green
    }
    else {
        Write-Warning "Failed to uninstall Python package (exit code: $LASTEXITCODE)"
    }
}
catch {
    Write-Warning "Error uninstalling Python package: $_"
}

# ============================================================================
# Step 3: Data Directory Handling
# ============================================================================

Write-Host "Checking data directory..." -ForegroundColor Green

$dataDir = Join-Path $env:APPDATA "claude-code-proxy"
$accountsFile = Join-Path $dataDir "data\accounts.json"

if (Test-Path $dataDir) {
    Write-Host ""
    Write-Host "⚠️  Data directory preserved at: $dataDir" -ForegroundColor Yellow
    Write-Host ""

    if (Test-Path $accountsFile) {
        Write-Host "Your OAuth accounts are preserved in:" -ForegroundColor Cyan
        Write-Host "  $accountsFile" -ForegroundColor White
        Write-Host ""
        Write-Host "To backup accounts before removing:" -ForegroundColor Cyan
        Write-Host "  Copy-Item '$accountsFile' -Destination ~\Desktop\accounts-backup.json" -ForegroundColor Yellow
        Write-Host ""
    }

    Write-Host "To manually remove all data:" -ForegroundColor Cyan
    Write-Host "  Remove-Item -Recurse -Force '$dataDir'" -ForegroundColor Yellow
    Write-Host ""
}

# ============================================================================
# Uninstallation Complete
# ============================================================================

Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║       Claude Code Proxy Uninstalled Successfully         ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Data directory preserved for safety." -ForegroundColor Cyan
Write-Host "Remove manually if no longer needed." -ForegroundColor Cyan
Write-Host ""
