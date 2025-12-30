# Chocolatey Package

This directory contains the Chocolatey package for installing Claude Code Proxy on Windows.

## Structure

- `claude-code-proxy.nuspec` - Package metadata
- `tools/chocolateyinstall.ps1` - Installation script
- `tools/chocolateyuninstall.ps1` - Uninstallation script

## Installation

Users will install with:
```powershell
choco install claude-code-proxy
```

## Development

To test the package locally:
```powershell
choco pack
choco install claude-code-proxy -s . -y
```

## References

- [Chocolatey Package Creation](https://docs.chocolatey.org/en-us/create/create-packages)
- [Python Packages in Chocolatey](https://docs.chocolatey.org/en-us/guides/create/create-python-packages)
