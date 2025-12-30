# GitHub Pages Setup

This document describes how to configure GitHub Pages for hosting the Claude Code Proxy installer script.

## Overview

GitHub Pages will host the installer script at `https://joachimbrindeau.github.io/claude-proxy-multi/install.sh`, allowing users to install with:

```bash
curl https://joachimbrindeau.github.io/claude-proxy-multi/install.sh | bash
```

## Required Configuration

### 1. Enable GitHub Pages

1. Navigate to repository **Settings** → **Pages**
2. Under **Source**, select:
   - **Branch**: `gh-pages`
   - **Folder**: `/ (root)`
3. Click **Save**

### 2. Configure Custom Domain

1. In the **Custom domain** field, enter: `joachimbrindeau.github.io/claude-proxy-multi/install.sh`
2. Click **Save**
3. Wait for DNS check to complete
4. Enable **Enforce HTTPS** (required for secure installations)

### 3. DNS Configuration

Configure your DNS provider with the following CNAME record:

```
Type:  CNAME
Name:  joachimbrindeau.github.io/claude-proxy-multi/install.sh
Value: joachimbrindeau.github.io
TTL:   3600 (or default)
```

**Verification**:
```bash
dig joachimbrindeau.github.io/claude-proxy-multi/install.sh CNAME +short
# Should return: joachimbrindeau.github.io
```

### 4. SSL Certificate

GitHub will automatically provision a Let's Encrypt SSL certificate for the custom domain. This may take up to 24 hours.

**Check status** in Settings → Pages:
- ✅ "Your site is published at https://joachimbrindeau.github.io/claude-proxy-multi/install.sh"
- ✅ "HTTPS" badge shown

## Deployment Workflow

The installer is deployed via [.github/workflows/deploy-installer.yml](../../.github/workflows/deploy-installer.yml):

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'scripts/install.sh'
```

**Triggers**:
- Pushes to `main` branch that modify `scripts/install.sh`
- Manual workflow dispatch

**Process**:
1. Copies `scripts/install.sh` to `index` (no extension for curl compatibility)
2. Adds CNAME file with `joachimbrindeau.github.io/claude-proxy-multi/install.sh`
3. Deploys to `gh-pages` branch
4. GitHub Pages serves it at custom domain

## Testing

After setup, verify the installer is accessible:

```bash
# Test with curl
curl -I https://joachimbrindeau.github.io/claude-proxy-multi/install.sh
# Should return: HTTP/2 200

# Test content
curl https://joachimbrindeau.github.io/claude-proxy-multi/install.sh | head -n 5
# Should show installer script header

# Test installation (dry-run)
curl https://joachimbrindeau.github.io/claude-proxy-multi/install.sh | bash -s -- --help
```

## Troubleshooting

### DNS Not Resolving

**Problem**: `dig joachimbrindeau.github.io/claude-proxy-multi/install.sh` returns no records

**Solution**:
1. Verify CNAME record is configured in DNS provider
2. Wait for DNS propagation (can take up to 48 hours)
3. Use `nslookup joachimbrindeau.github.io/claude-proxy-multi/install.sh 8.8.8.8` to test against Google DNS

### SSL Certificate Not Provisioning

**Problem**: "HTTPS" badge not showing in GitHub Pages settings

**Solution**:
1. Ensure DNS is properly configured (see above)
2. Disable and re-enable custom domain in GitHub Pages settings
3. Wait 24 hours for certificate provisioning
4. Check GitHub Pages settings for error messages

### 404 Not Found

**Problem**: `curl https://joachimbrindeau.github.io/claude-proxy-multi/install.sh` returns 404

**Solution**:
1. Verify `gh-pages` branch exists and contains `index` file
2. Check GitHub Actions workflow runs for deployment errors
3. Ensure "Source" is set to `gh-pages / (root)` in Pages settings

## Repository Settings Checklist

- [ ] GitHub Pages enabled on `gh-pages` branch
- [ ] Custom domain set to `joachimbrindeau.github.io/claude-proxy-multi/install.sh`
- [ ] DNS CNAME record configured
- [ ] HTTPS enforced
- [ ] SSL certificate provisioned (may take 24 hours)
- [ ] Test `curl https://joachimbrindeau.github.io/claude-proxy-multi/install.sh` returns installer script

## References

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Custom Domain Configuration](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)
- [DNS Configuration](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)
