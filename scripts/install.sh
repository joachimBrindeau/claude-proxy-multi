#!/usr/bin/env bash
# Claude Code Proxy - Docker Installer
# Usage: curl -fsSL https://joachimbrindeau.github.io/ccproxy-api/install.sh | bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_URL="https://raw.githubusercontent.com/joachimbrindeau/ccproxy-api/main/docker/compose.dist.yaml"
DATA_DIR="./data"
COMPOSE_FILE="docker-compose.yml"
HEALTH_ENDPOINT="http://localhost:8000/health"
WEB_UI_URL="http://localhost:8000/accounts"
MAX_HEALTH_CHECKS=30
HEALTH_CHECK_INTERVAL=2

# Banner
echo -e "${BLUE}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║        Claude Code Proxy - Docker Installation           ║"
echo "║                                                           ║"
echo "║  Multi-account Claude API proxy with automatic rotation  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to check command availability
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to open browser (platform-specific)
open_browser() {
    local url="$1"

    if command_exists xdg-open; then
        # Linux
        xdg-open "$url" &> /dev/null &
    elif command_exists open; then
        # macOS
        open "$url" &> /dev/null &
    elif command_exists start; then
        # Windows (Git Bash, WSL)
        start "$url" &> /dev/null &
    else
        # Fallback: just show the URL
        return 1
    fi
    return 0
}

echo -e "${BOLD}Step 1: Checking Prerequisites${NC}"
echo "─────────────────────────────────────"
echo ""

# Check for Docker
print_status "Checking for Docker..."
if ! command_exists docker; then
    print_error "Docker not found"
    echo ""
    echo "Please install Docker first:"
    echo "  macOS:   https://docs.docker.com/desktop/install/mac-install/"
    echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo "  Linux:   https://docs.docker.com/engine/install/"
    echo ""
    exit 1
fi

DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
print_success "Docker found (version $DOCKER_VERSION)"

# Check if Docker daemon is running
print_status "Checking Docker daemon..."
if ! docker ps &> /dev/null; then
    print_error "Docker daemon is not running"
    echo ""
    echo "Please start Docker Desktop or the Docker daemon and try again"
    exit 1
fi
print_success "Docker daemon is running"

# Check for docker-compose or docker compose
print_status "Checking for Docker Compose..."
if command_exists docker-compose; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f4 | tr -d ',')
    print_success "docker-compose found (version $COMPOSE_VERSION)"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VERSION=$(docker compose version --short)
    print_success "docker compose found (version $COMPOSE_VERSION)"
else
    print_error "Docker Compose not found"
    echo ""
    echo "Please install Docker Compose:"
    echo "  https://docs.docker.com/compose/install/"
    echo ""
    exit 1
fi

# Check for curl (needed for health check)
if ! command_exists curl; then
    print_warning "curl not found - skipping health check"
    SKIP_HEALTH_CHECK=true
else
    SKIP_HEALTH_CHECK=false
fi

echo ""
echo -e "${BOLD}Step 2: Setting Up Environment${NC}"
echo "─────────────────────────────────────"
echo ""

# Download docker-compose.yml
print_status "Downloading Docker Compose configuration..."
if curl -fsSL "$COMPOSE_URL" -o "$COMPOSE_FILE"; then
    print_success "Downloaded $COMPOSE_FILE"
else
    print_error "Failed to download compose file from $COMPOSE_URL"
    exit 1
fi

# Create data directory with restrictive permissions
print_status "Creating data directory..."
if [ -d "$DATA_DIR" ]; then
    print_warning "Data directory already exists at $DATA_DIR"
else
    mkdir -p "$DATA_DIR"
    chmod 700 "$DATA_DIR"
    print_success "Created $DATA_DIR with 700 permissions"
fi

echo ""
echo -e "${BOLD}Step 3: Starting Claude Code Proxy${NC}"
echo "─────────────────────────────────────"
echo ""

# Pull latest image
print_status "Pulling latest Docker image..."
if $COMPOSE_CMD pull; then
    print_success "Image pulled successfully"
else
    print_warning "Failed to pull image - will use cached version"
fi

# Start services
print_status "Starting services..."
if $COMPOSE_CMD up -d; then
    print_success "Services started"
else
    print_error "Failed to start services"
    echo ""
    echo "Check logs with:"
    echo "  $COMPOSE_CMD logs"
    exit 1
fi

# Wait for health check
if [ "$SKIP_HEALTH_CHECK" = false ]; then
    echo ""
    print_status "Waiting for Claude Code Proxy to become healthy..."

    for i in $(seq 1 $MAX_HEALTH_CHECKS); do
        if curl -fsSL "$HEALTH_ENDPOINT" &> /dev/null; then
            print_success "Health check passed!"
            HEALTH_CHECK_PASSED=true
            break
        fi

        # Show progress
        if [ $((i % 5)) -eq 0 ]; then
            echo -e "${BLUE}  ...${NC} Still waiting (${i}/${MAX_HEALTH_CHECKS})"
        fi

        sleep $HEALTH_CHECK_INTERVAL
    done

    if [ "${HEALTH_CHECK_PASSED:-false}" != true ]; then
        print_error "Health check failed after $((MAX_HEALTH_CHECKS * HEALTH_CHECK_INTERVAL)) seconds"
        echo ""
        echo "The service may still be starting. Check logs with:"
        echo "  $COMPOSE_CMD logs"
        echo ""
        echo "You can also check manually:"
        echo "  curl $HEALTH_ENDPOINT"
        exit 1
    fi
else
    print_warning "Skipped health check (curl not available)"
    echo ""
    echo "Waiting 10 seconds for service to start..."
    sleep 10
fi

# Installation complete
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              Installation Complete! 🎉                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo ""
echo "  1. Add your Claude accounts via the web UI:"
echo -e "     ${BLUE}→ $WEB_UI_URL${NC}"
echo ""
echo "  2. Use the proxy API:"
echo -e "     ${BLUE}→ http://localhost:8000/api/v1/messages${NC}"
echo ""
echo "  3. Check the SDK endpoints:"
echo -e "     ${BLUE}→ http://localhost:8000/sdk/v1/messages${NC}"
echo ""
echo -e "${BOLD}Useful Commands:${NC}"
echo ""
echo "  View logs:       $COMPOSE_CMD logs -f"
echo "  Stop service:    $COMPOSE_CMD down"
echo "  Restart service: $COMPOSE_CMD restart"
echo "  Check status:    $COMPOSE_CMD ps"
echo ""
echo -e "${BOLD}Documentation:${NC}"
echo "  https://github.com/joachimbrindeau/ccproxy-api"
echo ""

# Try to open browser
print_status "Opening web UI in browser..."
if open_browser "$WEB_UI_URL"; then
    print_success "Browser opened"
else
    print_warning "Could not auto-open browser"
    echo ""
    echo "Please open manually:"
    echo "  $WEB_UI_URL"
fi

echo ""
echo -e "${GREEN}Happy proxying! 🚀${NC}"
