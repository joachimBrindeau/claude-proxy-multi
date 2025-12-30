# GitHub Secrets Configuration

This document describes all GitHub secrets required for the Claude Code Proxy CI/CD pipeline.

## Overview

GitHub Actions workflows use secrets to authenticate with external services for:
- Package publishing (PyPI, Docker Hub, Homebrew)
- Cloud deployments (Railway, Render, Fly.io)
- Update notifications

## Required Secrets

### 1. PyPI Publishing

**Secret**: Not required ✨

**Reason**: Uses [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) with OpenID Connect (OIDC)

**Configuration**:
1. Log in to [PyPI](https://pypi.org/)
2. Navigate to account settings → Publishing
3. Add trusted publisher:
   - **Owner**: `joachimbrindeau`
   - **Repository**: `claude-proxy-multi`
   - **Workflow**: `release.yml`
   - **Environment**: `publish` (optional)

**Workflow usage**: Handled automatically via `id-token: write` permission

---

### 2. Docker Hub (Optional)

**Secret**: `DOCKERHUB_TOKEN`

**Purpose**: Publish Docker images to Docker Hub in addition to GitHub Container Registry

**How to create**:
1. Log in to [Docker Hub](https://hub.docker.com/)
2. Account Settings → Security → New Access Token
3. Token description: "GitHub Actions - Claude Code Proxy"
4. Access permissions: **Read, Write, Delete**
5. Copy token (shown only once)

**How to add to GitHub**:
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `DOCKERHUB_TOKEN`
4. Value: Paste token from Docker Hub
5. Click **Add secret**

**Workflow usage**:
```yaml
- name: Log in to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}
```

**Required additional secret**: `DOCKERHUB_USERNAME` (your Docker Hub username as plain text)

---

### 3. Homebrew Tap Publishing

**Secret**: `HOMEBREW_TAP_TOKEN`

**Purpose**: Update Homebrew formula in `joachimbrindeau/homebrew-claude-code-proxy` tap

**How to create**:
1. Generate GitHub Personal Access Token (PAT):
   - GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - Click **Generate new token**
   - Token name: "Homebrew Tap Updates - Claude Code Proxy"
   - Repository access: **Only select repositories** → `homebrew-claude-code-proxy`
   - Permissions:
     - **Contents**: Read and write
     - **Metadata**: Read-only (automatic)
   - Expiration: 1 year (maximum)
2. Copy token (shown only once)

**How to add to GitHub**:
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `HOMEBREW_TAP_TOKEN`
4. Value: Paste PAT
5. Click **Add secret**

**Workflow usage**:
```yaml
- name: Update Homebrew formula
  env:
    GITHUB_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}
  run: |
    # Update formula in homebrew-claude-code-proxy repository
```

---

### 4. Chocolatey Package Publishing

**Secret**: `CHOCO_API_KEY`

**Purpose**: Publish Windows packages to Chocolatey Community Repository

**How to create**:
1. Create Chocolatey account:
   - Go to [Chocolatey Community](https://community.chocolatey.org/)
   - Sign up or log in
2. Get API key:
   - Navigate to account settings
   - Click **API Keys** tab
   - Copy your API key (shown only once)

**How to add to GitHub**:
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `CHOCO_API_KEY`
4. Value: Paste API key from Chocolatey
5. Click **Add secret**

**Workflow usage**:
```yaml
- name: Publish to Chocolatey
  env:
    CHOCO_API_KEY: ${{ secrets.CHOCO_API_KEY }}
  run: |
    choco push package.nupkg --source https://push.chocolatey.org/ --api-key $env:CHOCO_API_KEY
```

**Package moderation**:
- First package submission requires manual approval (24-48 hours)
- Subsequent updates are automated
- Follow [Chocolatey package guidelines](https://docs.chocolatey.org/en-us/create/create-packages)

---

### 5. Snap Store Publishing (Linux)

**Secret**: `SNAPCRAFT_STORE_CREDENTIALS`

**Purpose**: Publish Snap packages to Snap Store for Linux distributions

**How to create**:

1. **Install Snapcraft**:
   ```bash
   sudo snap install snapcraft --classic
   ```

2. **Register package name** (one-time setup):
   ```bash
   snapcraft register claude-code-proxy
   ```
   - Package names are first-come, first-served
   - You must own the registered name to publish

3. **Login to Snap Store**:
   ```bash
   snapcraft login
   ```
   - Enter your Ubuntu One credentials
   - This authenticates your local snapcraft CLI

4. **Export credentials for CI/CD**:
   ```bash
   snapcraft export-login snapcraft-token.txt
   ```
   - This creates a base64-encoded credentials file
   - The token includes your authentication and upload permissions
   - Keep this file secure and never commit it to the repository

5. **Get credential content**:
   ```bash
   cat snapcraft-token.txt
   ```
   - Copy the entire output (it's a long base64 string)

**How to add to GitHub**:
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `SNAPCRAFT_STORE_CREDENTIALS`
4. Value: Paste the entire content from `snapcraft-token.txt`
5. Click **Add secret**

**Important**: Delete the local token file after adding to GitHub:
```bash
rm snapcraft-token.txt
```

**Workflow usage**:
```yaml
- name: Publish to Snap Store
  uses: snapcore/action-publish@v1
  env:
    SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT_STORE_CREDENTIALS }}
  with:
    snap: package.snap
    release: stable
```

**Channel management**:
- `stable`: Production releases (from version tags)
- `candidate`: Pre-release testing
- `beta`: Beta releases (from tags containing 'beta')
- `edge`: Development snapshots (from main branch)

**Publishing workflow**:
1. First submission requires manual review (24-72 hours)
2. After approval, subsequent updates are automatic
3. Stable channel releases are promoted from candidate
4. Follow [Snap Store publishing guidelines](https://snapcraft.io/docs/releasing-your-app)

**Security notes**:
- Credentials have upload permissions to all your registered snaps
- Rotate credentials annually or when team members change
- Monitor [Snap Store dashboard](https://dashboard.snapcraft.io/) for package status

---

### 6. Cloud Platform Deployments

#### Railway

**Secrets**: `RAILWAY_TOKEN`, `RAILWAY_PROJECT_ID`

**Purpose**: Automatic deployments to Railway.app

**How to create**:
1. [Railway CLI](https://docs.railway.app/develop/cli):
   ```bash
   railway login
   railway init  # Select project
   railway tokens create
   ```
2. Copy token
3. Get project ID:
   ```bash
   railway status
   # Project ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

**How to add to GitHub**:
- `RAILWAY_TOKEN`: API token from CLI
- `RAILWAY_PROJECT_ID`: Project ID from `railway status`

#### Render

**Secret**: `RENDER_API_KEY`

**Purpose**: Deploy Blueprint updates

**How to create**:
1. Log in to [Render Dashboard](https://dashboard.render.com/)
2. Account Settings → API Keys
3. Create API Key
4. Copy key

#### Fly.io

**Secret**: `FLY_API_TOKEN`

**Purpose**: Deploy via `flyctl deploy`

**How to create**:
```bash
flyctl auth token
```

---

### 7. Notification Services (Optional)

#### Slack Webhook

**Secret**: `SLACK_WEBHOOK_URL`

**Purpose**: Release notifications to Slack channel

**How to create**:
1. Slack → Apps → Incoming Webhooks
2. Add to workspace
3. Select channel
4. Copy webhook URL

#### Discord Webhook

**Secret**: `DISCORD_WEBHOOK_URL`

**Purpose**: Release notifications to Discord channel

**How to create**:
1. Discord → Server Settings → Integrations → Webhooks
2. New Webhook
3. Copy webhook URL

---

## Secret Management Best Practices

### Security

- ✅ **Use fine-grained tokens** with minimal required permissions
- ✅ **Set expiration dates** (max 1 year, rotate regularly)
- ✅ **Never commit secrets** to repository
- ✅ **Use environment-specific secrets** for staging vs production
- ⚠️ **Rotate secrets annually** or when team members leave

### Organization

**Secret naming convention**:
- Service name in UPPERCASE
- Descriptive suffix
- Example: `DOCKERHUB_TOKEN`, `HOMEBREW_TAP_TOKEN`

**Required vs Optional**:
- **Required**: PyPI trusted publisher config, HOMEBREW_TAP_TOKEN
- **Optional**: Docker Hub, cloud platforms, notifications

### Testing

Test secrets without exposing them:
```yaml
- name: Test secret availability
  run: |
    if [ -z "${{ secrets.DOCKERHUB_TOKEN }}" ]; then
      echo "⚠️ DOCKERHUB_TOKEN not configured - skipping Docker Hub publish"
    else
      echo "✅ DOCKERHUB_TOKEN configured"
    fi
```

---

## Secrets Checklist

Core deployment:
- [ ] PyPI trusted publisher configured
- [ ] `HOMEBREW_TAP_TOKEN` added (for macOS/Homebrew releases)
- [ ] `CHOCO_API_KEY` added (for Windows/Chocolatey releases)
- [ ] `SNAPCRAFT_STORE_CREDENTIALS` added (for Linux/Snap releases)

Optional enhancements:
- [ ] `DOCKERHUB_TOKEN` + `DOCKERHUB_USERNAME` (Docker Hub publishing)
- [ ] `RAILWAY_TOKEN` + `RAILWAY_PROJECT_ID` (Railway deployments)
- [ ] `RENDER_API_KEY` (Render deployments)
- [ ] `FLY_API_TOKEN` (Fly.io deployments)
- [ ] `SLACK_WEBHOOK_URL` (Slack notifications)
- [ ] `DISCORD_WEBHOOK_URL` (Discord notifications)

---

## Troubleshooting

### "Resource not accessible by integration"

**Problem**: Workflow cannot access secret

**Solutions**:
1. Verify secret name matches exactly (case-sensitive)
2. Check workflow has correct `permissions:` block
3. For PATs, verify token hasn't expired
4. For PATs, verify repository access permissions

### "Bad credentials"

**Problem**: Token is invalid or expired

**Solutions**:
1. Regenerate token in service (Docker Hub, GitHub PAT, etc.)
2. Update secret in GitHub repository settings
3. Verify token was copied completely (no trailing spaces)

### PyPI Trusted Publisher Issues

**Problem**: "Not a trusted publisher"

**Solutions**:
1. Verify PyPI trusted publisher configuration matches exactly:
   - Owner: `joachimbrindeau`
   - Repository: `claude-proxy-multi`
   - Workflow: `release.yml`
2. Ensure workflow uses `id-token: write` permission
3. Check workflow runs from the correct repository/branch

---

## References

- [GitHub Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [Docker Hub Access Tokens](https://docs.docker.com/docker-hub/access-tokens/)
- [GitHub Fine-grained PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
