# Binary Quick Start Guide

Download and run Claude Code Proxy in under 60 seconds.

## 1. Download

### macOS
```bash
curl -L -o claude-code-proxy https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-darwin-universal2
chmod +x claude-code-proxy
```

### Linux
```bash
curl -L -o claude-code-proxy https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-linux-amd64
chmod +x claude-code-proxy
```

### Windows (PowerShell)
```powershell
Invoke-WebRequest -Uri "https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-windows-amd64.exe" -OutFile "claude-code-proxy.exe"
```

## 2. Run

```bash
./claude-code-proxy serve
```

## 3. Add Account

Open http://localhost:8000/accounts and click "Add Account"

## Done!

Your proxy is now running and ready to use.

## Usage Examples

```bash
# Check version
./claude-code-proxy --version

# Start server (default port 8000)
./claude-code-proxy serve

# Custom port
./claude-code-proxy serve --port 8080

# With config file
./claude-code-proxy serve --config config.toml

# List accounts
./claude-code-proxy auth list

# Rotate accounts
./claude-code-proxy auth rotate

# Help
./claude-code-proxy --help
```

## Configuration

Create `config.toml`:
```toml
[server]
host = "0.0.0.0"
port = 8000

[rotation]
enabled = true
interval = 300
```

Run with config:
```bash
./claude-code-proxy serve --config config.toml
```

## Troubleshooting

### macOS: "Cannot be verified"
```bash
xattr -d com.apple.quarantine claude-code-proxy
```

### Linux: Permission denied
```bash
chmod +x claude-code-proxy
```

### Windows: Defender warning
Allow through Windows Security settings

## More Info

- 📖 [Full Installation Guide](./installation/binaries.md)
- 🐛 [Report Issues](https://github.com/joachimbrindeau/claude-code-proxy/issues)
- 📚 [Documentation](https://github.com/joachimbrindeau/claude-code-proxy/tree/main/docs)
