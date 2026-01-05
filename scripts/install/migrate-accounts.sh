#!/usr/bin/env bash
# Migrate OAuth accounts between Claude Code Proxy installations

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
FROM_URL=""
TO_URL=""
BACKUP_FILE="accounts-backup-$(date +%Y%m%d-%H%M%S).json"
DRY_RUN=false

# Usage information
usage() {
    cat << EOF
Usage: $0 --from SOURCE_URL --to DEST_URL [OPTIONS]

Migrate OAuth accounts from one Claude Code Proxy installation to another.

Required Arguments:
    --from URL      Source server URL (e.g., http://localhost:8080)
    --to URL        Destination server URL (e.g., https://new-server.com)

Optional Arguments:
    --backup FILE   Backup file path (default: accounts-backup-TIMESTAMP.json)
    --dry-run       Show what would be done without making changes
    -h, --help      Show this help message

Examples:
    # Migrate from local Docker to Railway
    $0 --from http://localhost:8080 --to https://my-app.railway.app

    # Migrate from old Homebrew install to new one
    $0 --from http://localhost:8080 --to http://localhost:9090

    # Dry run to see what would happen
    $0 --from http://old.example.com --to http://new.example.com --dry-run

EOF
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --from)
            FROM_URL="$2"
            shift 2
            ;;
        --to)
            TO_URL="$2"
            shift 2
            ;;
        --backup)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$FROM_URL" ] || [ -z "$TO_URL" ]; then
    echo -e "${RED}Error: --from and --to are required${NC}"
    usage
fi

# Check for curl
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed${NC}"
    exit 1
fi

echo -e "${BLUE}Claude Code Proxy Account Migration${NC}"
echo "======================================"
echo ""
echo "From: $FROM_URL"
echo "To:   $TO_URL"
echo "Backup: $BACKUP_FILE"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}Mode: DRY RUN (no changes will be made)${NC}"
fi
echo ""

# Step 1: Export accounts from source
echo -n "1. Exporting accounts from source... "
if ! EXPORT_DATA=$(curl -s -f "$FROM_URL/api/accounts" 2>&1); then
    echo -e "${RED}FAIL${NC}"
    echo "Error: Could not connect to source server"
    echo "Details: $EXPORT_DATA"
    exit 1
fi

# Validate JSON
if ! echo "$EXPORT_DATA" | python3 -m json.tool > /dev/null 2>&1; then
    echo -e "${RED}FAIL${NC}"
    echo "Error: Invalid JSON response from source"
    exit 1
fi

# Count accounts
ACCOUNT_COUNT=$(echo "$EXPORT_DATA" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['accounts']))")
echo -e "${GREEN}OK${NC} ($ACCOUNT_COUNT accounts)"

# Step 2: Save backup
echo -n "2. Saving backup to $BACKUP_FILE... "
echo "$EXPORT_DATA" > "$BACKUP_FILE"
echo -e "${GREEN}OK${NC}"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${YELLOW}DRY RUN: Would import $ACCOUNT_COUNT accounts to $TO_URL${NC}"
    echo "Backup saved to: $BACKUP_FILE"
    echo ""
    echo "To perform the actual migration, run without --dry-run"
    exit 0
fi

# Step 3: Import to destination
echo -n "3. Importing accounts to destination... "
if ! IMPORT_RESULT=$(curl -s -f -X POST "$TO_URL/api/accounts/import" \
    -H "Content-Type: application/json" \
    -d "$EXPORT_DATA" 2>&1); then
    echo -e "${RED}FAIL${NC}"
    echo "Error: Could not import to destination server"
    echo "Details: $IMPORT_RESULT"
    echo ""
    echo "Your accounts have been backed up to: $BACKUP_FILE"
    echo "You can manually import via the web UI at: $TO_URL/accounts"
    exit 1
fi

# Parse import result
IMPORTED=$(echo "$IMPORT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('imported', 0))" 2>/dev/null || echo "0")
UPDATED=$(echo "$IMPORT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('updated', 0))" 2>/dev/null || echo "0")
SKIPPED=$(echo "$IMPORT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('skipped', 0))" 2>/dev/null || echo "0")

echo -e "${GREEN}OK${NC}"
echo ""
echo -e "${GREEN}Migration completed successfully!${NC}"
echo "======================================"
echo "Imported: $IMPORTED new accounts"
echo "Updated:  $UPDATED existing accounts"
echo "Skipped:  $SKIPPED unchanged accounts"
echo ""
echo "Backup saved to: $BACKUP_FILE"
echo "Destination UI:  $TO_URL/accounts"
