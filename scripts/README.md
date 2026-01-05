# Installation Scripts

This directory contains helper scripts for installing and managing Claude Code Proxy across different platforms.

## Directory Structure

- `install/` - Platform-specific installation helpers
  - `check-requirements.sh` - Validate system requirements
  - `install-docker.sh` - Docker installation helper
  - `install-local.sh` - Local Python installation
  - `migrate-accounts.sh` - Account migration helper

## Usage

### Check System Requirements
```bash
./scripts/install/check-requirements.sh
```

### Docker Installation
```bash
./scripts/install/install-docker.sh
```

### Local Python Installation
```bash
./scripts/install/install-local.sh
```

### Migrate Accounts Between Installations
```bash
# Export from old installation
curl http://localhost:8080/api/accounts > accounts.json

# Import to new installation
curl -X POST http://new-server:8080/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json
```

Or use the migration script:
```bash
./scripts/install/migrate-accounts.sh \
  --from http://localhost:8080 \
  --to http://new-server:8080
```

## Development

All scripts should:
- Use `set -euo pipefail` for safety
- Include usage documentation
- Check for required dependencies
- Provide clear error messages
- Support dry-run mode where applicable
