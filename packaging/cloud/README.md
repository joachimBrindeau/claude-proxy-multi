# Cloud Platform Deployment

This directory contains deployment templates for cloud platforms.

## Supported Platforms

### Railway
- `railway.toml` - Railway configuration
- One-click deploy button in main README

### Render
- `render.yaml` - Render Blueprint
- One-click deploy button in main README

### Fly.io
- `fly.toml` - Fly.io configuration
- CLI deployment guide

## Quick Deploy

### Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/...)

### Render
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=...)

### Fly.io
```bash
flyctl launch
```

## Account Migration

All cloud deployments use the same `/data/accounts.json` format. You can:
1. Export accounts from local installation
2. Import via web UI at `https://your-app.railway.app/accounts`
3. Accounts automatically sync across container restarts

## References

- [Railway Documentation](https://docs.railway.app/)
- [Render Documentation](https://render.com/docs)
- [Fly.io Documentation](https://fly.io/docs/)
