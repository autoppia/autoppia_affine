#!/bin/bash
set -e

# =============================================================================
# Autoppia Affine Environment - Entrypoint Script
# =============================================================================
# This script:
# 1. Creates the Docker network if it doesn't exist
# 2. Starts demo website containers via docker-compose (DOOD pattern)
# 3. Waits for services to be healthy
# 4. Starts the FastAPI /evaluate server
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.webs.yml"
NETWORK_NAME="autoppia-net"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Check Docker socket availability
# =============================================================================
check_docker() {
    log_info "Checking Docker socket..."
    if [ ! -S /var/run/docker.sock ]; then
        log_error "Docker socket not found at /var/run/docker.sock"
        log_error "Make sure to mount the Docker socket: -v /var/run/docker.sock:/var/run/docker.sock"
        exit 1
    fi

    if ! docker info > /dev/null 2>&1; then
        log_error "Cannot connect to Docker daemon"
        exit 1
    fi

    log_success "Docker socket available"
}

# =============================================================================
# Create Docker network if not exists
# =============================================================================
ensure_network() {
    log_info "Ensuring Docker network '${NETWORK_NAME}' exists..."

    if ! docker network inspect "${NETWORK_NAME}" > /dev/null 2>&1; then
        docker network create "${NETWORK_NAME}"
        log_success "Created network '${NETWORK_NAME}'"
    else
        log_success "Network '${NETWORK_NAME}' already exists"
    fi
}

# =============================================================================
# Connect this container to the network
# =============================================================================
connect_self_to_network() {
    log_info "Connecting this container to '${NETWORK_NAME}'..."

    # Get current container ID
    CONTAINER_ID=$(cat /proc/self/cgroup 2>/dev/null | grep -oE '[0-9a-f]{64}' | head -1)

    if [ -z "$CONTAINER_ID" ]; then
        # Try alternative method
        CONTAINER_ID=$(hostname)
    fi

    if [ -n "$CONTAINER_ID" ]; then
        # Check if already connected
        if docker network inspect "${NETWORK_NAME}" --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | grep -q "$CONTAINER_ID"; then
            log_success "Already connected to '${NETWORK_NAME}'"
        else
            docker network connect "${NETWORK_NAME}" "$CONTAINER_ID" 2>/dev/null || true
            log_success "Connected to '${NETWORK_NAME}'"
        fi
    else
        log_warn "Could not determine container ID, skipping network connect"
    fi
}

# =============================================================================
# Start demo website containers
# =============================================================================
start_webs() {
    log_info "Starting demo website containers..."

    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "Compose file not found: ${COMPOSE_FILE}"
        exit 1
    fi

    # Check if containers are already running
    if docker ps --format '{{.Names}}' | grep -q "autoppia-webs-server"; then
        log_success "Demo website containers already running"
        return 0
    fi

    # Start containers using docker compose
    cd "${SCRIPT_DIR}"
    docker compose -f "${COMPOSE_FILE}" up -d --build

    log_success "Demo website containers started"
}

# =============================================================================
# Wait for services to be healthy
# =============================================================================
wait_for_services() {
    log_info "Waiting for services to be healthy..."

    local max_attempts=60
    local attempt=0

    # Wait for webs-server (check via docker inspect healthcheck status)
    log_info "Waiting for webs-server..."
    while [ $attempt -lt $max_attempts ]; do
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' autoppia-webs-server 2>/dev/null || echo "unknown")
        if [ "$HEALTH" = "healthy" ]; then
            log_success "webs-server is healthy"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        log_error "webs-server failed to become healthy"
        docker logs autoppia-webs-server --tail 50
        exit 1
    fi

    # Wait for web-autobooks (check via docker inspect healthcheck status)
    attempt=0
    log_info "Waiting for web-autobooks..."
    while [ $attempt -lt $max_attempts ]; do
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' autoppia-web-autobooks 2>/dev/null || echo "unknown")
        if [ "$HEALTH" = "healthy" ]; then
            log_success "web-autobooks is healthy"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        log_error "web-autobooks failed to become healthy"
        docker logs autoppia-web-autobooks --tail 50
        exit 1
    fi

    log_success "All services are healthy"
}

# =============================================================================
# Start port forwarding (socat)
# Routes localhost ports to Docker container ports
# =============================================================================
start_port_forwarding() {
    log_info "Starting port forwarding..."

    # Forward localhost:8001 → autoppia-web-autobooks:8001 (autobooks frontend)
    socat TCP-LISTEN:8001,fork,reuseaddr TCP:autoppia-web-autobooks:8001 &
    SOCAT_PID_8001=$!

    # Forward localhost:8080 → autoppia-webs-server:8080 (webs-server backend)
    socat TCP-LISTEN:8080,fork,reuseaddr TCP:autoppia-webs-server:8080 &
    SOCAT_PID_8080=$!

    # Add more port forwards here for additional websites:
    # socat TCP-LISTEN:8000,fork,reuseaddr TCP:autoppia-web-autocinema:8000 &

    sleep 1

    # Verify port forwarding is working
    if kill -0 $SOCAT_PID_8001 2>/dev/null && kill -0 $SOCAT_PID_8080 2>/dev/null; then
        log_success "Port forwarding started"
        echo "  localhost:8001 → autoppia-web-autobooks:8001"
        echo "  localhost:8080 → autoppia-webs-server:8080"
    else
        log_error "Port forwarding failed to start"
        exit 1
    fi
}

# =============================================================================
# Show service status
# =============================================================================
show_status() {
    echo ""
    log_info "=== Service Status ==="
    echo ""
    docker ps --filter "name=autoppia-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    log_info "=== Network Info ==="
    echo ""
    echo "  webs-server:   http://localhost:8080 (→ autoppia-webs-server:8080)"
    echo "  web-autobooks: http://localhost:8001 (→ autoppia-web-autobooks:8001)"
    echo ""
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo ""
    echo "=============================================="
    echo "  Autoppia Affine Environment - Starting"
    echo "=============================================="
    echo ""

    check_docker
    ensure_network
    connect_self_to_network
    start_webs
    wait_for_services
    start_port_forwarding
    show_status

    log_info "Starting FastAPI /evaluate server on port 8000..."
    echo ""

    # Start the FastAPI server
    exec uvicorn env:app --host 0.0.0.0 --port 8000
}

# Handle shutdown gracefully
cleanup() {
    log_info "Shutting down..."
    # Note: We don't stop the sibling containers here as they may be used by other instances
    # To fully clean up, run: docker compose -f docker-compose.webs.yml down
    exit 0
}

trap cleanup SIGTERM SIGINT

main "$@"
