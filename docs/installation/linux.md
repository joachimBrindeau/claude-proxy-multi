# Linux Installation Guide

This guide covers installing Claude Code Proxy on Linux using various methods.

## Table of Contents

- [Snap Package (Recommended)](#snap-package-recommended)
- [pip Installation](#pip-installation)
- [Docker](#docker)
- [From Source](#from-source)
- [Service Management](#service-management)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## Snap Package (Recommended)

Snap is the recommended installation method for most Linux distributions. It provides automatic updates and sandboxed execution.

### Supported Distributions

- Ubuntu 16.04 LTS and later
- Debian 9 and later
- Fedora
- openSUSE
- Arch Linux
- Manjaro
- Linux Mint
- Elementary OS
- Zorin OS
- and many more

[Full list of supported distributions](https://snapcraft.io/docs/installing-snapd)

### Prerequisites

Install snapd if not already available:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install snapd

# Fedora
sudo dnf install snapd

# Arch/Manjaro
sudo pacman -S snapd
sudo systemctl enable --now snapd.socket

# openSUSE
sudo zypper addrepo --refresh https://download.opensuse.org/repositories/system:/snappy/openSUSE_Leap_15.2 snappy
sudo zypper --gpg-auto-import-keys refresh
sudo zypper dup --from snappy
sudo zypper install snapd
```

### Installation

Install Claude Code Proxy from the Snap Store:

```bash
sudo snap install claude-code-proxy
```

The service starts automatically after installation.

### Verify Installation

Check that the service is running:

```bash
# Check service status
snap services claude-code-proxy

# View logs
snap logs claude-code-proxy.daemon

# Access web UI
curl http://localhost:8000/health
```

Open the web UI in your browser:
```
http://localhost:8000/accounts
```

### Snap Permissions

The snap has the following permissions (plugs):

- `network`: Outbound network access to Claude API
- `network-bind`: Listen on port 8000 for the web UI
- `home`: Read/write access to `$HOME/snap/claude-code-proxy/common/data`

### Data Location

Snap stores data in a sandboxed directory:

```bash
# Account data
~/snap/claude-code-proxy/common/data/accounts.json

# Configuration
~/snap/claude-code-proxy/common/config/

# Logs
sudo journalctl -u snap.claude-code-proxy.daemon
```

### Service Management

```bash
# Start service
sudo snap start claude-code-proxy.daemon

# Stop service
sudo snap stop claude-code-proxy.daemon

# Restart service
sudo snap restart claude-code-proxy.daemon

# View service status
snap services claude-code-proxy

# View logs (real-time)
snap logs -f claude-code-proxy.daemon

# View logs (last 100 lines)
snap logs -n 100 claude-code-proxy.daemon
```

### Updates

Snaps update automatically by default. You can also manually update:

```bash
# Check for updates
sudo snap refresh --list

# Update claude-code-proxy
sudo snap refresh claude-code-proxy

# View refresh schedule
snap refresh --time

# Disable automatic updates (not recommended)
sudo snap refresh --hold claude-code-proxy
```

### Channel Management

Choose your update channel:

```bash
# Stable (default) - Production releases
sudo snap install claude-code-proxy

# Candidate - Pre-release testing
sudo snap install claude-code-proxy --candidate

# Beta - Beta releases
sudo snap install claude-code-proxy --beta

# Edge - Latest development builds
sudo snap install claude-code-proxy --edge

# Switch channels
sudo snap refresh claude-code-proxy --channel=edge
```

### Using the CLI

Run CLI commands:

```bash
# Main CLI
claude-code-proxy --help

# Start API server manually
claude-code-proxy api

# Permission management
claude-code-proxy.perm --help
```

---

## pip Installation

Install using pip for more control over the Python environment.

### Prerequisites

- Python 3.11 or later
- pip (Python package installer)

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Fedora
sudo dnf install python3 python3-pip

# Arch/Manjaro
sudo pacman -S python python-pip
```

### Installation

Install in a virtual environment (recommended):

```bash
# Create virtual environment
python3 -m venv ~/claude-code-proxy-venv

# Activate virtual environment
source ~/claude-code-proxy-venv/bin/activate

# Install claude-code-proxy
pip install claude-code-proxy

# Verify installation
claude-code-proxy --version
```

Or install globally:

```bash
# Install globally (requires sudo)
sudo pip install claude-code-proxy

# Verify installation
claude-code-proxy --version
```

### Running as a Service

Create a systemd service file for automatic startup:

```bash
sudo nano /etc/systemd/system/claude-code-proxy.service
```

Add the following content:

```ini
[Unit]
Description=Claude Code Proxy Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username
Environment="PATH=/home/your-username/claude-code-proxy-venv/bin"
ExecStart=/home/your-username/claude-code-proxy-venv/bin/claude-code-proxy api
Restart=on-failure
RestartSec=5s

# Data directory
Environment="CLAUDE_CODE_PROXY_DATA_DIR=/home/your-username/.local/share/claude-code-proxy/data"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-code-proxy

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service on boot
sudo systemctl enable claude-code-proxy

# Start service
sudo systemctl start claude-code-proxy

# Check status
sudo systemctl status claude-code-proxy

# View logs
sudo journalctl -u claude-code-proxy -f
```

---

## Docker

Run Claude Code Proxy in a Docker container.

### Prerequisites

Install Docker:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# Fedora
sudo dnf install docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# Arch/Manjaro
sudo pacman -S docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Log out and back in for group changes to take effect.

### Run Container

```bash
# Pull latest image
docker pull ghcr.io/joachimbrindeau/claude-proxy-multi:latest

# Run container
docker run -d \
  --name claude-code-proxy \
  -p 8000:8000 \
  -v claude-code-proxy-data:/app/data \
  --restart unless-stopped \
  ghcr.io/joachimbrindeau/claude-proxy-multi:latest

# Check status
docker ps

# View logs
docker logs -f claude-code-proxy
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  claude-code-proxy:
    image: ghcr.io/joachimbrindeau/claude-proxy-multi:latest
    container_name: claude-code-proxy
    ports:
      - "8000:8000"
    volumes:
      - claude-code-proxy-data:/app/data
    restart: unless-stopped
    environment:
      - LOG_LEVEL=INFO

volumes:
  claude-code-proxy-data:
```

Run with Docker Compose:

```bash
# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down
```

See [Docker Installation Guide](docker.md) for more details.

---

## From Source

Build and install from source for development or custom builds.

### Prerequisites

Install build dependencies:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install git python3 python3-pip python3-venv build-essential

# Fedora
sudo dnf install git python3 python3-pip gcc make

# Arch/Manjaro
sudo pacman -S git python python-pip base-devel
```

### Installation Steps

```bash
# Clone repository
git clone https://github.com/joachimbrindeau/claude-proxy-multi.git
cd claude-proxy-multi

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Verify installation
claude-code-proxy --version

# Start server
claude-code-proxy api
```

### Building a Snap Locally

Build and install the snap package:

```bash
# Install snapcraft
sudo snap install snapcraft --classic

# Build snap
cd packaging/snap
snapcraft

# Install locally
sudo snap install ./claude-code-proxy_*.snap --dangerous

# View service status
snap services claude-code-proxy
```

---

## Service Management

### Snap Service

```bash
# Start
sudo snap start claude-code-proxy.daemon

# Stop
sudo snap stop claude-code-proxy.daemon

# Restart
sudo snap restart claude-code-proxy.daemon

# Status
snap services claude-code-proxy

# Logs
snap logs claude-code-proxy.daemon -f
```

### Systemd Service (pip installation)

```bash
# Start
sudo systemctl start claude-code-proxy

# Stop
sudo systemctl stop claude-code-proxy

# Restart
sudo systemctl restart claude-code-proxy

# Status
sudo systemctl status claude-code-proxy

# Enable on boot
sudo systemctl enable claude-code-proxy

# Disable on boot
sudo systemctl disable claude-code-proxy

# Logs
sudo journalctl -u claude-code-proxy -f
```

### Docker Service

```bash
# Start
docker start claude-code-proxy

# Stop
docker stop claude-code-proxy

# Restart
docker restart claude-code-proxy

# Logs
docker logs -f claude-code-proxy

# Remove
docker rm -f claude-code-proxy
```

---

## Configuration

### Environment Variables

Configure via environment variables:

```bash
# Data directory
export CLAUDE_CODE_PROXY_DATA_DIR=/path/to/data

# Config directory
export CLAUDE_CODE_PROXY_CONFIG_DIR=/path/to/config

# API port
export PORT=8000

# Log level
export LOG_LEVEL=INFO

# Start server
claude-code-proxy api
```

### Snap Configuration

For snap installations, set environment variables in the service file:

```bash
# View current snap configuration
snap get claude-code-proxy

# Set configuration (not available for environment variables)
# Environment variables must be set in snapcraft.yaml
```

### Systemd Configuration

Edit `/etc/systemd/system/claude-code-proxy.service`:

```ini
[Service]
Environment="CLAUDE_CODE_PROXY_DATA_DIR=/custom/path/data"
Environment="PORT=8080"
Environment="LOG_LEVEL=DEBUG"
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart claude-code-proxy
```

### Custom Port

Change the default port (8000):

**Snap:**
```bash
# Modify snapcraft.yaml before building
# Or use iptables to redirect
sudo iptables -t nat -A PREROUTING -p tcp --dport 8080 -j REDIRECT --to-port 8000
```

**Systemd:**
```bash
# Edit service file
sudo nano /etc/systemd/system/claude-code-proxy.service

# Add environment variable
Environment="PORT=8080"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart claude-code-proxy
```

**Docker:**
```bash
# Change port mapping
docker run -d -p 8080:8000 ghcr.io/joachimbrindeau/claude-proxy-multi:latest
```

---

## Troubleshooting

### Service Not Starting

**Check service status:**
```bash
# Snap
snap services claude-code-proxy
snap logs claude-code-proxy.daemon -n 50

# Systemd
sudo systemctl status claude-code-proxy
sudo journalctl -u claude-code-proxy -n 50

# Docker
docker ps -a
docker logs claude-code-proxy
```

**Common issues:**

1. **Port already in use:**
   ```bash
   # Find process using port 8000
   sudo lsof -i :8000
   sudo netstat -tulpn | grep 8000

   # Kill the process or change port
   sudo kill -9 <PID>
   ```

2. **Permission denied:**
   ```bash
   # Snap - check plugs are connected
   snap connections claude-code-proxy

   # Systemd - check file permissions
   ls -la /home/your-username/.local/share/claude-code-proxy/

   # Fix permissions
   chmod -R 755 /home/your-username/.local/share/claude-code-proxy/
   ```

3. **Python version mismatch:**
   ```bash
   # Check Python version
   python3 --version

   # Requires Python 3.11+
   # Install newer Python or use snap/docker
   ```

### Web UI Not Accessible

**Check if service is running:**
```bash
# Test locally
curl http://localhost:8000/health

# Check if port is listening
sudo netstat -tulpn | grep 8000
```

**Firewall issues:**
```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 8000/tcp
sudo ufw reload

# Fedora/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Check firewall status
sudo ufw status
sudo firewall-cmd --list-ports
```

### Snap Permission Issues

**Connect required plugs:**
```bash
# View connections
snap connections claude-code-proxy

# Manually connect plugs (usually automatic)
sudo snap connect claude-code-proxy:network
sudo snap connect claude-code-proxy:network-bind
sudo snap connect claude-code-proxy:home
```

### Service Crashes on Startup

**Check logs for errors:**
```bash
# Snap
snap logs claude-code-proxy.daemon -n 100

# Systemd
sudo journalctl -u claude-code-proxy -n 100 --no-pager

# Docker
docker logs claude-code-proxy
```

**Common errors:**

1. **Missing data directory:**
   ```bash
   # Snap (automatic)
   ls -la ~/snap/claude-code-proxy/common/data/

   # Systemd - create manually
   mkdir -p ~/.local/share/claude-code-proxy/data
   ```

2. **Corrupted accounts.json:**
   ```bash
   # Backup and reset
   mv ~/.local/share/claude-code-proxy/data/accounts.json ~/.local/share/claude-code-proxy/data/accounts.json.bak

   # Service will create new file on restart
   ```

### Snap Refresh Issues

**Check refresh status:**
```bash
# View refresh schedule
snap refresh --time

# Check for pending refreshes
sudo snap refresh --list

# Manual refresh
sudo snap refresh claude-code-proxy

# Check refresh hold
snap info claude-code-proxy | grep hold
```

### Performance Issues

**Check resource usage:**
```bash
# CPU and memory
top -p $(pgrep -f claude-code-proxy)

# Snap-specific
snap services claude-code-proxy
```

**Optimize performance:**
```bash
# Increase log level to reduce I/O
export LOG_LEVEL=WARNING

# For systemd, edit service file
Environment="LOG_LEVEL=WARNING"
```

---

## Uninstallation

### Remove Snap Package

```bash
# Stop and remove service
sudo snap remove claude-code-proxy

# Remove data (optional)
rm -rf ~/snap/claude-code-proxy
```

### Remove pip Installation

```bash
# Stop service (if using systemd)
sudo systemctl stop claude-code-proxy
sudo systemctl disable claude-code-proxy

# Remove service file
sudo rm /etc/systemd/system/claude-code-proxy.service
sudo systemctl daemon-reload

# Uninstall package
pip uninstall claude-code-proxy

# Remove virtual environment
rm -rf ~/claude-code-proxy-venv

# Remove data (optional)
rm -rf ~/.local/share/claude-code-proxy
```

### Remove Docker Container

```bash
# Stop and remove container
docker stop claude-code-proxy
docker rm claude-code-proxy

# Remove image
docker rmi ghcr.io/joachimbrindeau/claude-proxy-multi

# Remove volume (data)
docker volume rm claude-code-proxy-data
```

---

## Additional Resources

- [Main Documentation](../../README.md)
- [Docker Installation](docker.md)
- [Cloud Deployment](cloud.md)
- [GitHub Repository](https://github.com/joachimbrindeau/claude-proxy-multi)
- [Issue Tracker](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
- [Snap Store Page](https://snapcraft.io/claude-code-proxy)

---

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Search [existing issues](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
3. Check service logs for error messages
4. Create a [new issue](https://github.com/joachimbrindeau/claude-proxy-multi/issues/new) with:
   - Linux distribution and version
   - Installation method (snap/pip/docker/source)
   - Relevant logs
   - Steps to reproduce

---

## Security Notes

- The service runs on `localhost:8000` by default (not exposed externally)
- For production deployments, use a reverse proxy (nginx, Apache) with HTTPS
- Snap confinement provides sandboxed execution for enhanced security
- Never commit credentials or `accounts.json` to version control
- Use firewall rules to restrict access if needed

---

## Next Steps

After installation:

1. **Access the Web UI**: Open http://localhost:8000/accounts
2. **Add Accounts**: Click "Add Account" and enter Claude credentials
3. **Test the Proxy**: Send a test request to verify functionality
4. **Configure Auto-start**: Enable the service to start on boot
5. **Monitor Logs**: Check logs regularly for errors or issues
6. **Set Up Backups**: Regularly backup your `accounts.json` file

Enjoy using Claude Code Proxy!
