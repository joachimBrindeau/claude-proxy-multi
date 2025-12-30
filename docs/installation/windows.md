# Windows Installation Guide

Install Claude Code Proxy on Windows using Chocolatey for native package management with automatic Windows Service registration.

## Quick Start

**Install with Chocolatey**:
```powershell
choco install claude-code-proxy
```

**Start the service**:
```powershell
Start-Service claude-code-proxy
```

**Open web UI**:
```
http://localhost:8000/accounts
```

**Installation time**: ~3 minutes ⚡

---

## Prerequisites

### Required

- **Windows** 10 or later, OR **Windows Server** 2016 or later
- **Chocolatey** package manager ([Install Chocolatey](https://chocolatey.org/install))
- **Python** 3.11+ (automatically installed as dependency)

### Optional

- **Administrator privileges** (for service management)

---

## Installation

### Step 1: Install Chocolatey (if not installed)

Open PowerShell as Administrator and run:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

Verify installation:
```powershell
choco --version
```

### Step 2: Install Claude Code Proxy

```powershell
choco install claude-code-proxy
```

This will:
- Install Python 3.11 (if not already installed)
- Install `claude-code-proxy` Python package from PyPI
- Register Windows Service (`claude-code-proxy`)
- Create data directory at `%APPDATA%\claude-code-proxy\data`
- Set service to Manual startup (requires explicit start)

### Step 3: Start the Service

```powershell
Start-Service claude-code-proxy
```

The service will:
- Start on http://localhost:8000
- Run as LocalSystem account
- Automatically restart on failure
- Log to Windows Event Log

### Step 4: Verify Installation

Check service status:
```powershell
Get-Service claude-code-proxy
```

Expected output:
```
Status   Name               DisplayName
------   ----               -----------
Running  claude-code-proxy  Claude Code Proxy
```

Check health endpoint:
```powershell
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## Adding Claude Accounts

After installation, configure your Claude accounts:

1. **Open the web UI**:
   ```
   http://localhost:8000/accounts
   ```

2. **Add accounts via OAuth** (same process as other installations)

3. **Accounts persist** across restarts in:
   ```
   %APPDATA%\claude-code-proxy\data\accounts.json
   ```

---

## Usage

### Proxy API

Use with the Anthropic SDK:

**Python**:
```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000/api",
    api_key="any-value"  # Ignored, using OAuth
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello from Windows!"}]
)
```

**PowerShell**:
```powershell
$headers = @{
    "Content-Type" = "application/json"
    "x-api-key" = "any-value"
}

$body = @{
    model = "claude-sonnet-4-20250514"
    max_tokens = 1024
    messages = @(
        @{
            role = "user"
            content = "Hello from Windows!"
        }
    )
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/messages" -Method Post -Headers $headers -Body $body
```

### SDK Endpoints

Direct endpoints (bypass Anthropic SDK):

```powershell
# Messages
POST http://localhost:8000/sdk/v1/messages

# Models
GET http://localhost:8000/sdk/v1/models
```

---

## Service Management

### Start Service
```powershell
Start-Service claude-code-proxy
```

### Stop Service
```powershell
Stop-Service claude-code-proxy
```

### Restart Service
```powershell
Restart-Service claude-code-proxy
```

### Check Status
```powershell
Get-Service claude-code-proxy | Format-List *
```

### View Service Configuration
```powershell
Get-WmiObject -Class Win32_Service -Filter "Name='claude-code-proxy'" | Format-List *
```

### Set Automatic Startup
```powershell
Set-Service -Name claude-code-proxy -StartupType Automatic
Start-Service claude-code-proxy
```

---

## Configuration

### Change Port

The port is configured in the service startup parameters. To change:

1. **Stop the service**:
   ```powershell
   Stop-Service claude-code-proxy
   ```

2. **Modify service binary path**:
   ```powershell
   $exePath = (Get-WmiObject -Class Win32_Service -Filter "Name='claude-code-proxy'").PathName
   # Extract path without arguments
   $exeOnly = $exePath -replace ' --.*$', ''

   # Set new port
   sc.exe config claude-code-proxy binPath= "$exeOnly --host 0.0.0.0 --port 9000"
   ```

3. **Start the service**:
   ```powershell
   Start-Service claude-code-proxy
   ```

### Change Log Level

Set via environment variable:

1. **Create environment variable**:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('SERVER__LOG_LEVEL', 'DEBUG', 'Machine')
   ```

2. **Restart service** to apply:
   ```powershell
   Restart-Service claude-code-proxy
   ```

Available log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### Data Directory

Default location:
```
%APPDATA%\claude-code-proxy\data\
```

Accounts file:
```
%APPDATA%\claude-code-proxy\data\accounts.json
```

To view full path:
```powershell
Write-Host "$env:APPDATA\claude-code-proxy\data"
```

---

## Updating

### Update to Latest Version

```powershell
choco upgrade claude-code-proxy
```

This will:
1. Stop the service
2. Uninstall old version
3. Install new version
4. Preserve data directory and accounts
5. Re-register service with same configuration

### Check for Updates

```powershell
choco outdated
```

### Pin Version (Prevent Updates)

```powershell
choco pin add -n=claude-code-proxy
```

### Unpin Version

```powershell
choco pin remove -n=claude-code-proxy
```

---

## Logs and Debugging

### Windows Event Log

View service logs:

```powershell
Get-EventLog -LogName Application -Source "claude-code-proxy" -Newest 50
```

Filter by severity:
```powershell
# Errors only
Get-EventLog -LogName Application -Source "claude-code-proxy" -EntryType Error

# Warnings and errors
Get-EventLog -LogName Application -Source "claude-code-proxy" -EntryType Warning,Error
```

### Debug Mode

Run service in foreground for debugging:

1. **Stop the service**:
   ```powershell
   Stop-Service claude-code-proxy
   ```

2. **Find executable location**:
   ```powershell
   $service = Get-WmiObject -Class Win32_Service -Filter "Name='claude-code-proxy'"
   $exePath = $service.PathName -replace ' --.*$', ''
   $exePath = $exePath.Trim('"')
   ```

3. **Run manually with debug logging**:
   ```powershell
   $env:SERVER__LOG_LEVEL = "DEBUG"
   & $exePath --host 0.0.0.0 --port 8000
   ```

4. **Press Ctrl+C to stop**, then restart service:
   ```powershell
   Start-Service claude-code-proxy
   ```

---

## Backup and Restore

### Backup Accounts

**Via API**:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/accounts" | ConvertTo-Json | Out-File "$HOME\Desktop\claude-proxy-backup.json"
```

**Direct file copy**:
```powershell
Copy-Item "$env:APPDATA\claude-code-proxy\data\accounts.json" -Destination "$HOME\Desktop\claude-proxy-backup.json"
```

### Restore Accounts

**Via web UI**:
1. Open http://localhost:8000/accounts
2. Click "Import Accounts"
3. Select backup file

**Direct file copy**:
```powershell
Stop-Service claude-code-proxy
Copy-Item "$HOME\Desktop\claude-proxy-backup.json" -Destination "$env:APPDATA\claude-code-proxy\data\accounts.json" -Force
Start-Service claude-code-proxy
```

---

## Troubleshooting

### Port Already in Use

**Problem**: `Address already in use: bind`

**Solution**: Change port (see Configuration section) or stop conflicting service:

```powershell
# Find process using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object -Property OwningProcess

# Stop the process (replace PID with actual process ID)
Stop-Process -Id <PID> -Force
```

### Service Won't Start

**Problem**: `Start-Service` fails

**Solutions**:

1. Check Event Log:
   ```powershell
   Get-EventLog -LogName Application -Source "claude-code-proxy" -Newest 10 | Format-List
   ```

2. Verify Python installation:
   ```powershell
   python --version
   # Should show Python 3.11+
   ```

3. Reinstall package:
   ```powershell
   choco uninstall claude-code-proxy
   choco install claude-code-proxy
   ```

4. Check permissions:
   ```powershell
   # Run PowerShell as Administrator
   Get-Service claude-code-proxy | Format-List *
   ```

### Installation Fails

**Problem**: `choco install` fails

**Solutions**:

1. Run PowerShell as Administrator

2. Update Chocolatey:
   ```powershell
   choco upgrade chocolatey
   ```

3. Clear Chocolatey cache:
   ```powershell
   choco cache clear
   ```

4. Retry with verbose output:
   ```powershell
   choco install claude-code-proxy --verbose
   ```

### Cannot Access Web UI

**Problem**: `http://localhost:8000` not loading

**Solutions**:

1. Verify service is running:
   ```powershell
   Get-Service claude-code-proxy
   ```

2. Check if port is accessible:
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 8000
   ```

3. Check Windows Firewall:
   ```powershell
   # Allow port 8000 inbound
   New-NetFirewallRule -DisplayName "Claude Code Proxy" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```

4. Try 127.0.0.1 instead:
   ```
   http://127.0.0.1:8000/accounts
   ```

### Python Import Errors

**Problem**: Event Log shows `ModuleNotFoundError`

**Solutions**:

1. Reinstall package:
   ```powershell
   choco uninstall claude-code-proxy
   choco install claude-code-proxy
   ```

2. Check Python packages:
   ```powershell
   python -m pip list | Select-String "claude"
   ```

3. Verify Python installation:
   ```powershell
   where.exe python
   python --version
   ```

---

## Migration

### From Docker/Homebrew to Windows

**Step 1**: Export accounts from old installation
```bash
curl http://old-server:8000/api/accounts > accounts.json
```

**Step 2**: Install on Windows
```powershell
choco install claude-code-proxy
Start-Service claude-code-proxy
```

**Step 3**: Import accounts
- Open http://localhost:8000/accounts
- Click "Import Accounts"
- Select `accounts.json`

### From Windows to Another Method

Export accounts before uninstalling:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/accounts" | ConvertTo-Json | Out-File "$HOME\Desktop\accounts-backup.json"
```

---

## Uninstallation

### Remove Package Only

```powershell
choco uninstall claude-code-proxy
```

Data remains at `%APPDATA%\claude-code-proxy\`

### Complete Removal (Including Data)

```powershell
# Uninstall package
choco uninstall claude-code-proxy

# Remove data directory
Remove-Item -Recurse -Force "$env:APPDATA\claude-code-proxy"
```

---

## Advanced Topics

### Using with VS Code

Configure VS Code to use the proxy:

**settings.json**:
```json
{
  "anthropic.baseURL": "http://localhost:8000/api"
}
```

### Running as Different User

By default, the service runs as LocalSystem. To change:

```powershell
Stop-Service claude-code-proxy

# Set to run as NetworkService
sc.exe config claude-code-proxy obj= "NT AUTHORITY\NetworkService"

# Or run as specific user (requires password)
sc.exe config claude-code-proxy obj= "DOMAIN\Username" password= "Password"

Start-Service claude-code-proxy
```

### Multiple Instances

Run multiple proxy instances on different ports:

1. **Install normally**:
   ```powershell
   choco install claude-code-proxy
   ```

2. **Create second service**:
   ```powershell
   $exePath = "C:\Users\<Username>\AppData\Roaming\Python\Python311\Scripts\claude-code-proxy-api.exe"

   New-Service `
     -Name "claude-code-proxy-secondary" `
     -BinaryPathName "$exePath --host 0.0.0.0 --port 9000" `
     -DisplayName "Claude Code Proxy (Secondary)" `
     -StartupType Manual

   Start-Service claude-code-proxy-secondary
   ```

3. **Access at different ports**:
   - Primary: http://localhost:8000
   - Secondary: http://localhost:9000

### Network Access

Allow access from other machines:

1. **Configure Windows Firewall**:
   ```powershell
   New-NetFirewallRule `
     -DisplayName "Claude Code Proxy - Inbound" `
     -Direction Inbound `
     -LocalPort 8000 `
     -Protocol TCP `
     -Action Allow
   ```

2. **Access from network**:
   ```
   http://<windows-machine-ip>:8000/accounts
   ```

---

## Comparison with Other Methods

| Feature | Chocolatey | Docker | Homebrew |
|---------|------------|--------|----------|
| **Installation** | 3 min | 1 min | 2 min |
| **Auto-start** | ✅ Service | ✅ Container | ✅ Service |
| **Updates** | `choco upgrade` | `docker pull` | `brew upgrade` |
| **System Integration** | ✅ Native | ⚠️ Container | ✅ Native |
| **Resource Usage** | Low | Medium | Low |
| **Best For** | Windows users | Cross-platform | macOS users |

---

## Next Steps

- 📖 [API Documentation](../api/README.md)
- 🔧 [Configuration Guide](../configuration/README.md)
- 🐳 [Docker Installation](./docker.md)
- 🍺 [Homebrew Installation](./homebrew.md)
- ☁️ [Cloud Deployment](./cloud.md)
- 💬 [Get Help](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
