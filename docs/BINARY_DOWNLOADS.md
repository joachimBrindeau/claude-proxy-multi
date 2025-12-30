# Claude Code Proxy - Standalone Binaries

Download and run Claude Code Proxy without installing Python or any dependencies.

## Quick Download

Choose your platform:

| Platform | Download | SHA256 Checksum |
|----------|----------|-----------------|
| **macOS** (Universal) | [claude-code-proxy-darwin-universal2](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-darwin-universal2) | See [checksums.txt](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/checksums.txt) |
| **Linux** (x86_64) | [claude-code-proxy-linux-amd64](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-linux-amd64) | See [checksums.txt](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/checksums.txt) |
| **Windows** (x86_64) | [claude-code-proxy-windows-amd64.exe](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-windows-amd64.exe) | See [checksums.txt](https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/checksums.txt) |

## Installation

### macOS
```bash
# Download
curl -L -o claude-code-proxy \
  https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-darwin-universal2

# Make executable
chmod +x claude-code-proxy

# Run
./claude-code-proxy --version
```

### Linux
```bash
# Download
curl -L -o claude-code-proxy \
  https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-linux-amd64

# Make executable
chmod +x claude-code-proxy

# Run
./claude-code-proxy --version
```

### Windows (PowerShell)
```powershell
# Download
Invoke-WebRequest -Uri "https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/claude-code-proxy-windows-amd64.exe" `
  -OutFile "claude-code-proxy.exe"

# Run
.\claude-code-proxy.exe --version
```

## Quick Start

1. **Download** the binary for your platform
2. **Run** the server:
   ```bash
   ./claude-code-proxy serve
   ```
3. **Open** http://localhost:8000/accounts in your browser
4. **Add** your Claude account via OAuth
5. **Use** the proxy with any Claude Code client

## Verify Download

Download and verify checksums:

```bash
# Download checksums
curl -L -O https://github.com/joachimbrindeau/claude-code-proxy/releases/latest/download/checksums.txt

# Verify (Linux/macOS)
sha256sum -c checksums.txt

# Verify (Windows PowerShell)
Get-FileHash claude-code-proxy-windows-amd64.exe -Algorithm SHA256
```

## System Requirements

- **macOS**: macOS 11 (Big Sur) or later, Intel or Apple Silicon
- **Linux**: x86_64, glibc 2.17+ (Ubuntu 14.04+, RHEL 7+)
- **Windows**: Windows 10 or later (64-bit)

## Full Documentation

For detailed installation instructions, troubleshooting, and advanced usage:

📖 [Complete Binary Installation Guide](./installation/binaries.md)

## Alternative Installation Methods

- **pip**: `pip install claude-code-proxy`
- **Docker**: `docker pull ghcr.io/joachimbrindeau/claude-code-proxy`
- **Homebrew** (macOS): `brew install joachimbrindeau/claude-code-proxy/claude-code-proxy`

See [all installation options](./installation/) for more details.

## Support

- 📚 [Documentation](https://github.com/joachimbrindeau/claude-code-proxy/tree/main/docs)
- 🐛 [Report Issues](https://github.com/joachimbrindeau/claude-code-proxy/issues)
- 💬 [Discussions](https://github.com/joachimbrindeau/claude-code-proxy/discussions)

## What's Included

Each binary is a self-contained executable that includes:
- Claude Code Proxy server
- Web UI for account management
- All required dependencies
- No Python installation needed

**Size**: Approximately 70-110 MB per binary

## License

MIT License - See [LICENSE](../LICENSE) for details.
