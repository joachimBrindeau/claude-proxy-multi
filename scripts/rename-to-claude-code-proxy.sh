#!/bin/bash
# Comprehensive renaming script: ccproxy → claude-code-proxy
# This script renames the package, module paths, and all references throughout the codebase

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 Starting comprehensive renaming: ccproxy → claude-code-proxy"
echo "   Working directory: $PROJECT_ROOT"

# Step 1: Rename source directory
echo ""
echo "📁 Step 1/6: Renaming source directory"
if [ -d "src/ccproxy" ]; then
    mv src/ccproxy src/claude_code_proxy
    echo "   ✓ Renamed src/ccproxy → src/claude_code_proxy"
else
    echo "   ⚠ src/ccproxy not found (may already be renamed)"
fi

# Step 2: Update all Python imports
echo ""
echo "🐍 Step 2/6: Updating Python imports"
find src tests -type f -name "*.py" -exec sed -i '' \
    -e 's/from ccproxy\./from claude_code_proxy./g' \
    -e 's/import ccproxy\./import claude_code_proxy./g' \
    -e 's/from ccproxy import/from claude_code_proxy import/g' \
    -e 's/import ccproxy$/import claude_code_proxy/g' \
    {} +
echo "   ✓ Updated Python imports in src/ and tests/"

# Step 3: Update Docker configuration files
echo ""
echo "🐳 Step 3/6: Updating Docker configurations"
for file in docker/compose.yaml docker/compose.local.yaml docker/compose.dist.yaml; do
    if [ -f "$file" ]; then
        sed -i '' 's/ccproxy/claude-code-proxy/g' "$file"
        echo "   ✓ Updated $file"
    fi
done

# Step 4: Update configuration files
echo ""
echo "⚙️  Step 4/6: Updating configuration files"
if [ -f ".pre-commit-config.yaml" ]; then
    sed -i '' 's/ccproxy/claude_code_proxy/g' .pre-commit-config.yaml
    echo "   ✓ Updated .pre-commit-config.yaml"
fi

# Step 5: Update documentation
echo ""
echo "📚 Step 5/6: Updating documentation"
for file in README.md docs/CHANGELOG.md docs/TESTING.md runtime/README.md; do
    if [ -f "$file" ]; then
        sed -i '' \
            -e 's/ccproxy-api/claude-code-proxy/g' \
            -e 's/ccproxy/claude-code-proxy/g' \
            -e 's/CCProxy/Claude Code Proxy/g' \
            "$file"
        echo "   ✓ Updated $file"
    fi
done

# Step 6: Update deployment scripts
echo ""
echo "🚀 Step 6/6: Updating deployment scripts"
if [ -f "deploy/scripts/format_version.py" ]; then
    sed -i '' 's/ccproxy/claude_code_proxy/g' deploy/scripts/format_version.py
    echo "   ✓ Updated deploy/scripts/format_version.py"
fi

# Verification
echo ""
echo "🔍 Verification: Checking for remaining 'ccproxy' references"
echo "   Excluding: specs/, .git/, __pycache__/, .mypy_cache/, node_modules/, this script"

remaining=$(find . -type f \
    \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.md" -o -name "*.sh" \) \
    ! -path "*/specs/*" \
    ! -path "*/.git/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.mypy_cache/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/scripts/rename-to-claude-code-proxy.sh" \
    -exec grep -l "ccproxy" {} + 2>/dev/null || true)

if [ -z "$remaining" ]; then
    echo "   ✅ No remaining 'ccproxy' references found!"
else
    echo "   ⚠️  Found remaining references in:"
    echo "$remaining" | sed 's/^/      - /'
    echo ""
    echo "   You may want to manually review these files."
fi

echo ""
echo "✨ Renaming complete!"
echo ""
echo "Next steps:"
echo "  1. Review changes with: git diff"
echo "  2. Run tests: pytest"
echo "  3. Check imports: python -c 'import claude_code_proxy'"
echo "  4. Commit changes: git add -A && git commit -m 'refactor: rename ccproxy to claude-code-proxy'"
