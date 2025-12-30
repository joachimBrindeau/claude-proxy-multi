# Installing Claude Code Proxy - Standalone Binaries

Standalone binaries provide a simple way to run Claude Code Proxy without installing Python or any dependencies. Just download, extract, and run.

## Quick Start

### 1. Download the Binary

Download the appropriate binary for your platform from the [latest release](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest):

- **macOS**: `claude-code-proxy-darwin-universal2`
- **Linux**: `claude-code-proxy-linux-amd64`
- **Windows**: `claude-code-proxy-windows-amd64.exe`

### 2. Make it Executable (macOS/Linux only)

```bash
chmod +x claude-code-proxy-*
```

### 3. Run the Binary

**macOS/Linux:**
```bash
./claude-code-proxy-darwin-universal2 --version
```

**Windows:**
```powershell
.\claude-code-proxy-windows-amd64.exe --version
```

## Installation Methods

### Option 1: Download via Browser

1. Go to [Releases](https://github.com/joachimbrindeau/claude-code-proxy/releases)
2. Download the binary for your platform
3. Move to a convenient location
4. Make executable (macOS/Linux)

### Option 2: Download via Command Line

**macOS/Linux:**
```bash
# Set the platform suffix
PLATFORM="darwin-universal2"  # or "linux-amd64"

# Download the latest release
curl -L -o claude-code-proxy \
  "https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-${PLATFORM}"

# Make executable
chmod +x claude-code-proxy

# Move to PATH (optional)
sudo mv claude-code-proxy /usr/local/bin/
```

**Windows (PowerShell):**
```powershell
# Download the latest release
Invoke-WebRequest -Uri "https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-windows-amd64.exe" `
  -OutFile "claude-code-proxy.exe"

# Move to PATH (optional)
Move-Item claude-code-proxy.exe "$env:USERPROFILE\bin\"
```

## System Requirements

### Minimum Requirements
- **macOS**: macOS 11 (Big Sur) or later, Intel or Apple Silicon
- **Linux**: x86_64 architecture, glibc 2.17 or later
- **Windows**: Windows 10 or later (64-bit)

### Disk Space
- Approximately 50-100 MB per binary

### Memory
- Minimum: 512 MB RAM
- Recommended: 1 GB RAM or more

## Usage

Once installed, the binary works exactly like the Python package:

```bash
# Start the server
claude-code-proxy serve

# With custom port
claude-code-proxy serve --port 8080

# With configuration file
claude-code-proxy serve --config config.toml

# Manage accounts
claude-code-proxy auth add
claude-code-proxy auth list
claude-code-proxy auth rotate

# View help
claude-code-proxy --help
```

## Verification

Verify the binary is working correctly:

```bash
# Check version
claude-code-proxy --version

# Start server
claude-code-proxy serve

# In another terminal, test the API
curl http://localhost:8000/health
```

Expected output:
```json
{"status": "healthy"}
```

## First Run

On first run, the binary will:

1. Create configuration directory at `~/.claude-code-proxy/`
2. Initialize credential storage
3. Start the web UI at http://localhost:8000/accounts

### Add Your First Account

1. Open http://localhost:8000/accounts in your browser
2. Click "Add Account"
3. Follow the OAuth flow to authenticate with Claude
4. Your credentials are securely stored

## Platform-Specific Notes

### macOS

**Gatekeeper Warning:**
If you see "cannot be opened because the developer cannot be verified":

```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine claude-code-proxy-darwin-universal2

# Or allow in System Preferences
# System Preferences > Security & Privacy > General > "Open Anyway"
```

**Code Signing:**
The binary is not currently code-signed. This is a known limitation and will be addressed in future releases.

### Linux

**Missing Libraries:**
If you encounter "version 'GLIBC_X.XX' not found":

```bash
# Check your glibc version
ldd --version

# On older systems, you may need to install from source or use Docker
```

**Permissions:**
If you get permission errors:

```bash
# Make sure the binary is executable
chmod +x claude-code-proxy-linux-amd64

# Run with explicit path
./claude-code-proxy-linux-amd64
```

### Windows

**Windows Defender:**
The binary may be flagged by Windows Defender. To allow:

1. Open Windows Security
2. Click "Virus & threat protection"
3. Click "Manage settings"
4. Add an exclusion for the binary

**Firewall:**
You may need to allow the binary through Windows Firewall:

1. Windows will prompt on first run
2. Click "Allow access"

## Updating

To update to a new version:

```bash
# Download the new binary
curl -L -o claude-code-proxy-new \
  "https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-${PLATFORM}"

# Replace the old binary
mv claude-code-proxy-new claude-code-proxy
chmod +x claude-code-proxy
```

Your configuration and credentials are stored separately and will not be affected.

## Uninstallation

To completely remove Claude Code Proxy:

```bash
# Remove binary
rm /usr/local/bin/claude-code-proxy  # or wherever you installed it

# Remove configuration and credentials (optional)
rm -rf ~/.claude-code-proxy/
```

## Troubleshooting

### Binary Won't Start

**Check file permissions:**
```bash
ls -l claude-code-proxy-*
# Should show: -rwxr-xr-x
```

**Run with verbose logging:**
```bash
LOG_LEVEL=DEBUG ./claude-code-proxy serve
```

### Port Already in Use

```bash
# Use a different port
claude-code-proxy serve --port 8080
```

### Cannot Connect to Web UI

**Check if server is running:**
```bash
curl http://localhost:8000/health
```

**Check firewall settings:**
- Ensure port 8000 is not blocked by your firewall
- Try accessing via http://127.0.0.1:8000/accounts

### Performance Issues

**Increase memory:**
The binary includes all dependencies and may use more memory than the Python package.

**Check resource usage:**
```bash
# macOS
top -pid $(pgrep claude-code-proxy)

# Linux
htop -p $(pgrep claude-code-proxy)

# Windows
tasklist /FI "IMAGENAME eq claude-code-proxy.exe"
```

## Security Considerations

### Binary Verification

**Checksums:**
Each release includes SHA256 checksums:

```bash
# Download checksum file
curl -L -O "https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/checksums.txt"

# Verify (macOS/Linux)
sha256sum -c checksums.txt
```

### Credential Storage

The binary uses the same secure credential storage as the Python package:
- **macOS**: Keychain
- **Linux**: Secret Service / Keyring
- **Windows**: Credential Manager

If keyring is not available, credentials are stored encrypted in `~/.claude-code-proxy/credentials.json`.

## Comparison with Other Installation Methods

| Method | Pros | Cons |
|--------|------|------|
| **Binary** | ✅ No Python required<br>✅ Single file<br>✅ Fast startup | ❌ Larger file size<br>❌ Not code-signed (macOS) |
| **pip** | ✅ Smaller download<br>✅ Easy updates<br>✅ Standard Python tool | ❌ Requires Python<br>❌ Dependency conflicts |
| **Docker** | ✅ Isolated<br>✅ Reproducible | ❌ Requires Docker<br>❌ More complex |
| **Homebrew** | ✅ Easy updates<br>✅ macOS native | ❌ macOS only |

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Search [existing issues](https://github.com/joachimbrindeau/claude-code-proxy/issues)
3. Open a [new issue](https://github.com/joachimbrindeau/claude-code-proxy/issues/new) with:
   - Binary version (`claude-code-proxy --version`)
   - Operating system and version
   - Full error message
   - Steps to reproduce

## Advanced Usage

### Running as a Service

**systemd (Linux):**
```ini
# /etc/systemd/system/claude-code-proxy.service
[Unit]
Description=Claude Code Proxy
After=network.target

[Service]
Type=simple
User=your-user
ExecStart=/usr/local/bin/claude-code-proxy serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable claude-code-proxy
sudo systemctl start claude-code-proxy
```

**launchd (macOS):**
```xml
<!-- ~/Library/LaunchAgents/com.claude-code-proxy.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-code-proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/claude-code-proxy</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.claude-code-proxy.plist
```

**Windows Service:**
Use [NSSM](https://nssm.cc/) to create a Windows service:

```powershell
# Download and install NSSM
nssm install claude-code-proxy "C:\path\to\claude-code-proxy.exe" "serve"
nssm start claude-code-proxy
```

### Configuration

The binary reads configuration from:
1. Command-line arguments (highest priority)
2. Config file specified with `--config`
3. Environment variables
4. Default values

Example `config.toml`:
```toml
[server]
host = "0.0.0.0"
port = 8000

[auth]
storage = "keyring"  # or "json"

[rotation]
enabled = true
interval = 300  # seconds
```

Run with config:
```bash
claude-code-proxy serve --config config.toml
```

## Next Steps

- Read the [Configuration Guide](../configuration.md)
- Learn about [Account Management](../accounts.md)
- Set up [Reverse Proxy](../deployment/reverse-proxy.md)
- Configure [Docker Integration](../deployment/docker.md)
