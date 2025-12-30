#!/bin/bash
# Second pass: Update string literals, environment variables, and comments
# This handles references that weren't caught by the import updates

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔧 Second pass: Updating string literals and environment variables"
echo "   Working directory: $PROJECT_ROOT"

# Step 1: Update environment variable names in source code
echo ""
echo "🌍 Step 1/4: Updating environment variable names"
find src tests -type f -name "*.py" -exec sed -i '' \
    -e 's/CCPROXY_/CLAUDE_CODE_PROXY_/g' \
    -e 's/ccproxy\./claude_code_proxy./g' \
    -e 's/"ccproxy"/"claude_code_proxy"/g' \
    -e "s/'ccproxy'/'claude_code_proxy'/g" \
    -e 's/__name__ == "claude_code_proxy/__name__ == "claude_code_proxy/g' \
    {} +
echo "   ✓ Updated environment variable names in Python files"

# Step 2: Update package/module names in strings and comments
echo ""
echo "📝 Step 2/4: Updating string literals and comments"
find src tests -type f -name "*.py" -exec sed -i '' \
    -e 's/package ccproxy/package claude_code_proxy/g' \
    -e 's/module ccproxy/module claude_code_proxy/g' \
    -e 's/the ccproxy/the claude_code_proxy/g' \
    -e 's/CCProxy API/Claude Code Proxy API/g' \
    -e 's/ccproxy API/claude-code-proxy API/g' \
    {} +
echo "   ✓ Updated string literals and comments"

# Step 3: Update GitHub workflows
echo ""
echo "⚙️  Step 3/4: Updating GitHub workflows"
find .github/workflows -type f -name "*.yml" -exec sed -i '' \
    -e 's/ccproxy/claude-code-proxy/g' \
    -e 's/CCPROXY_/CLAUDE_CODE_PROXY_/g' \
    {} +
echo "   ✓ Updated GitHub workflow files"

# Step 4: Update test fixture documentation
echo ""
echo "🧪 Step 4/4: Updating test fixtures"
if [ -f "tests/fixtures/README.md" ]; then
    sed -i '' \
        -e 's/ccproxy/claude-code-proxy/g' \
        -e 's/CCProxy/Claude Code Proxy/g' \
        tests/fixtures/README.md
    echo "   ✓ Updated tests/fixtures/README.md"
fi

# Verification
echo ""
echo "🔍 Final verification: Checking for remaining 'ccproxy' references"

remaining=$(find . -type f \
    \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.md" \) \
    ! -path "*/specs/*" \
    ! -path "*/.git/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.mypy_cache/*" \
    ! -path "*/.venv/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/scripts/*.sh" \
    -exec grep -l "ccproxy" {} + 2>/dev/null || true)

if [ -z "$remaining" ]; then
    echo "   ✅ No remaining 'ccproxy' references found!"
else
    echo "   📋 Remaining references (may be intentional):"
    echo "$remaining" | sed 's/^/      - /'
    echo ""
    echo "   Showing context for remaining occurrences:"
    while IFS= read -r file; do
        echo ""
        echo "   📄 $file:"
        grep -n "ccproxy" "$file" | head -3 | sed 's/^/      /'
    done <<< "$remaining"
fi

echo ""
echo "✨ String and variable update complete!"
