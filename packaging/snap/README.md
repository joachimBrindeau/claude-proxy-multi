# Snap Package

This directory contains the Snap package for installing Claude Code Proxy on Linux distributions.

## Structure

- `snapcraft.yaml` - Snap package definition
- `snap/` - Snap hooks and scripts

## Installation

Users will install with:
```bash
sudo snap install claude-code-proxy
```

## Development

To build the snap locally:
```bash
snapcraft
sudo snap install ./claude-code-proxy_*.snap --dangerous
```

## References

- [Snapcraft Documentation](https://snapcraft.io/docs)
- [Python Snaps Guide](https://snapcraft.io/docs/python-apps)
- [Snap Hooks](https://snapcraft.io/docs/supported-snap-hooks)
