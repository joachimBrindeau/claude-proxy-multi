# Homebrew Formula

This directory contains the Homebrew formula for installing Claude Code Proxy on macOS and Linux.

## Structure

- `claude-code-proxy.rb` - Main Homebrew formula
- `tap/` - Custom tap for hosting the formula (optional)

## Installation

Users will install with:
```bash
brew install claude-code-proxy
```

## Development

To test the formula locally:
```bash
brew install --build-from-source ./claude-code-proxy.rb
```

## References

- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Python Formula Guide](https://docs.brew.sh/Python-for-Formula-Authors)
