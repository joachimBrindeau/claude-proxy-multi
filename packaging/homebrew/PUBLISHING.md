# Homebrew Formula Publishing Guide

This guide explains how to create and maintain the Homebrew tap for Claude Code Proxy.

## Overview

Homebrew uses "taps" (third-party repositories) to distribute formulas. Our tap is:
- **Repository**: `joachimbrindeau/homebrew-claude-code-proxy`
- **Formula**: `claude-code-proxy.rb`
- **Installation**: `brew install joachimbrindeau/claude-code-proxy/claude-code-proxy`

## One-Time Setup

### Step 1: Create Tap Repository

Create a new public repository for the tap:

```bash
gh repo create joachimbrindeau/homebrew-claude-code-proxy \
  --public \
  --description "Homebrew tap for Claude Code Proxy" \
  --homepage "https://github.com/joachimbrindeau/claude-proxy-multi"
```

**Repository naming convention**: `homebrew-<tap-name>`
- Tap name: `claude-code-proxy`
- Repository: `homebrew-claude-code-proxy`
- Users tap it with: `brew tap joachimbrindeau/claude-code-proxy`

### Step 2: Initialize Tap Structure

```bash
# Clone the new tap repository
git clone https://github.com/joachimbrindeau/homebrew-claude-code-proxy.git
cd homebrew-claude-code-proxy

# Create Formula directory
mkdir Formula

# Create README
cat > README.md << 'EOF'
# Homebrew Tap for Claude Code Proxy

Official Homebrew tap for [Claude Code Proxy](https://github.com/joachimbrindeau/claude-proxy-multi).

## Installation

```bash
brew install joachimbrindeau/claude-code-proxy/claude-code-proxy
```

## Usage

Start the service:
```bash
brew services start claude-code-proxy
```

Access the web UI:
```
http://localhost:8080/accounts
```

## Documentation

- [Installation Guide](https://github.com/joachimbrindeau/claude-proxy-multi/blob/main/docs/installation/homebrew.md)
- [Main Repository](https://github.com/joachimbrindeau/claude-proxy-multi)

## Support

Report issues at: https://github.com/joachimbrindeau/claude-proxy-multi/issues
EOF

# Commit and push
git add .
git commit -m "Initial tap structure"
git push origin main
```

### Step 3: Copy Formula

```bash
# From main repository
cp packaging/homebrew/claude-code-proxy.rb \
   ../homebrew-claude-code-proxy/Formula/

cd ../homebrew-claude-code-proxy
git add Formula/claude-code-proxy.rb
git commit -m "Add claude-code-proxy formula v0.1.0"
git push
```

### Step 4: Test Installation

```bash
# Tap the repository
brew tap joachimbrindeau/claude-code-proxy

# Install the formula
brew install claude-code-proxy

# Verify installation
claude-code-proxy-api --version

# Test service
brew services start claude-code-proxy
curl http://localhost:8080/health

# Check logs
tail -f /opt/homebrew/var/log/claude-code-proxy/stdout.log
```

## Updating the Formula

### Manual Update (for testing)

```bash
cd homebrew-claude-code-proxy

# Update formula file
vim Formula/claude-code-proxy.rb

# Update version, URL, and SHA256
# Version: 0.2.0
# URL: https://files.pythonhosted.org/packages/.../claude-code-proxy-0.2.0.tar.gz
# SHA256: (download file and run: shasum -a 256 file.tar.gz)

# Commit and push
git add Formula/claude-code-proxy.rb
git commit -m "Update claude-code-proxy to v0.2.0"
git push
```

### Automated Update (CI/CD)

The GitHub Actions workflow automatically updates the formula on each release:

**File**: `.github/workflows/release.yml`

```yaml
update-homebrew:
  needs: [build-package]  # Wait for PyPI publish
  runs-on: macos-latest
  steps:
    - name: Update Homebrew formula
      env:
        HOMEBREW_GITHUB_API_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}
      run: |
        brew tap joachimbrindeau/claude-code-proxy
        brew bump-formula-pr \
          --no-browse \
          --no-audit \
          joachimbrindeau/claude-code-proxy/claude-code-proxy \
          --url https://files.pythonhosted.org/packages/source/c/claude-code-proxy/claude-code-proxy-${{ github.ref_name }}.tar.gz
```

**Note**: `brew bump-formula-pr` automatically:
- Downloads the new tarball
- Calculates SHA256
- Updates the formula
- Creates a pull request (or commits directly if you own the tap)

## Regenerating Python Dependencies

When dependencies change in `pyproject.toml`, regenerate the resource blocks:

**Method 1: Using homebrew-pypi-poet**

```bash
# Create temp environment
cd /tmp
python3 -m venv venv
source venv/bin/activate

# Install package and poet
pip install claude-code-proxy homebrew-pypi-poet

# Generate resource stanzas
poet claude-code-proxy > resources.txt

# Copy output into Formula/claude-code-proxy.rb
# Replace the resource blocks with generated content
```

**Method 2: Using brew update-python-resources (preferred)**

```bash
# From homebrew-claude-code-proxy directory
brew update-python-resources Formula/claude-code-proxy.rb
```

This automatically updates all `resource` blocks in the formula.

## Testing the Formula

### Local Testing

```bash
# Install from local formula
brew install --build-from-source ./Formula/claude-code-proxy.rb

# Test formula
brew test claude-code-proxy

# Audit formula
brew audit --new-formula claude-code-proxy

# Style check
brew style claude-code-proxy
```

### CI Testing

Add to `.github/workflows/homebrew-test.yml`:

```yaml
name: Test Homebrew Formula

on:
  pull_request:
    paths:
      - 'packaging/homebrew/claude-code-proxy.rb'

jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install formula
        run: |
          brew install --build-from-source packaging/homebrew/claude-code-proxy.rb

      - name: Test formula
        run: |
          brew test packaging/homebrew/claude-code-proxy.rb

      - name: Audit formula
        run: |
          brew audit --new-formula packaging/homebrew/claude-code-proxy.rb
```

## Troubleshooting

### Formula Fails to Install

**Problem**: `Error: Failed to download resource`

**Solutions**:
1. Verify PyPI URL is correct
2. Check SHA256 matches downloaded file
3. Ensure version in URL matches formula version

### Service Won't Start

**Problem**: `brew services start` fails

**Solutions**:
1. Check logs: `tail -f /opt/homebrew/var/log/claude-code-proxy/stderr.log`
2. Verify port 8080 is available
3. Check Python dependencies installed correctly
4. Test manually: `/opt/homebrew/bin/claude-code-proxy-api --help`

### Dependencies Out of Date

**Problem**: Formula installs but runtime errors

**Solutions**:
1. Regenerate dependencies: `brew update-python-resources Formula/claude-code-proxy.rb`
2. Verify `pyproject.toml` has correct versions
3. Test in fresh virtualenv before publishing

## Publishing Checklist

Before publishing a new formula version:

- [ ] Package published to PyPI
- [ ] PyPI URL and SHA256 verified
- [ ] Dependencies regenerated if changed
- [ ] Formula tests pass locally
- [ ] `brew audit` passes
- [ ] `brew style` passes
- [ ] Service starts successfully
- [ ] Health check responds
- [ ] Web UI accessible at http://localhost:8080/accounts
- [ ] Formula committed to tap repository
- [ ] Tag matches PyPI version

## References

- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Python Formula Guide](https://docs.brew.sh/Python-for-Formula-Authors)
- [Creating Taps](https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap)
- [homebrew-pypi-poet](https://github.com/tdsmith/homebrew-pypi-poet)
