#!/usr/bin/env bash
# Check system requirements for Claude Code Proxy installation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0

echo "Checking Claude Code Proxy system requirements..."
echo ""

# Check Python version
echo -n "Checking Python version... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        echo -e "${GREEN}OK${NC} (Python $PYTHON_VERSION)"
    else
        echo -e "${RED}FAIL${NC} (Python $PYTHON_VERSION - requires 3.11+)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}FAIL${NC} (Python 3 not found)"
    ERRORS=$((ERRORS + 1))
fi

# Check pip
echo -n "Checking pip... "
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
    echo -e "${GREEN}OK${NC} (pip $PIP_VERSION)"
else
    echo -e "${YELLOW}WARNING${NC} (pip3 not found - will use python -m pip)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check for virtual environment support
echo -n "Checking venv module... "
if python3 -m venv --help &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC} (venv module not available)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check available disk space
echo -n "Checking disk space... "
AVAILABLE_KB=$(df -k . | tail -1 | awk '{print $4}')
AVAILABLE_MB=$((AVAILABLE_KB / 1024))
if [ "$AVAILABLE_MB" -gt 500 ]; then
    echo -e "${GREEN}OK${NC} (${AVAILABLE_MB}MB available)"
else
    echo -e "${YELLOW}WARNING${NC} (${AVAILABLE_MB}MB available - recommend 500MB+)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check for curl (needed for OAuth and updates)
echo -n "Checking curl... "
if command -v curl &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC} (curl not found - needed for OAuth flow)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check for git (optional, for development)
echo -n "Checking git... "
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "${GREEN}OK${NC} (git $GIT_VERSION)"
else
    echo -e "${YELLOW}INFO${NC} (git not found - only needed for development)"
fi

# Summary
echo ""
echo "----------------------------------------"
if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}All requirements met!${NC}"
    echo "You can proceed with installation."
    exit 0
elif [ "$ERRORS" -eq 0 ]; then
    echo -e "${YELLOW}Requirements met with $WARNINGS warning(s)${NC}"
    echo "Installation should work, but some features may be limited."
    exit 0
else
    echo -e "${RED}Missing $ERRORS required component(s)${NC}"
    echo "Please install the missing requirements before proceeding."
    exit 1
fi
