#!/bin/bash
# =============================================================================
# Local Test Script for Autoppia Affine Environment
# =============================================================================
# This script builds and runs the self-contained affine environment locally.
#
# Prerequisites:
#   - Docker installed and running
#   - Docker socket accessible at /var/run/docker.sock
#
# Usage:
#   ./test_local.sh [build|run|test|clean|all]
#
# Commands:
#   build  - Build the Docker image
#   run    - Run the container (starts demo webs + FastAPI server)
#   test   - Test the /evaluate endpoint
#   clean  - Stop and remove all autoppia containers
#   all    - Build, run, and test (default)
# =============================================================================

set -e

IMAGE_NAME="autoppia-affine-env"
CONTAINER_NAME="autoppia-affine-env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

build() {
    log_info "Building Docker image..."
    cd "${SCRIPT_DIR}/.."
    docker build -t "${IMAGE_NAME}" -f autoppia_affine/Dockerfile .
    log_success "Image built: ${IMAGE_NAME}"
}

run() {
    log_info "Starting container..."

    # Stop existing container if running
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    # Run the container with Docker socket mounted
    docker run -d \
        --name "${CONTAINER_NAME}" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -p 8000:8000 \
        "${IMAGE_NAME}"

    log_success "Container started: ${CONTAINER_NAME}"
    log_info "Waiting for services to initialize (this may take 1-2 minutes on first run)..."

    # Wait for the FastAPI server to be ready
    local max_attempts=60
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_success "FastAPI server is ready at http://localhost:8000"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 5
    done

    log_error "Timeout waiting for FastAPI server"
    log_info "Showing container logs:"
    docker logs "${CONTAINER_NAME}" --tail 100
    return 1
}

test_endpoint() {
    log_info "Testing /health endpoint..."

    HEALTH_RESPONSE=$(curl -sf http://localhost:8000/health 2>&1)
    if [ $? -eq 0 ]; then
        log_success "Health check passed: ${HEALTH_RESPONSE}"
    else
        log_error "Health check failed"
        return 1
    fi

    log_info "Testing /evaluate endpoint (with mock model URL)..."
    log_warn "Note: /evaluate will fail without a real model endpoint, but validates the setup"

    # Test that the endpoint responds (even if the model call fails)
    EVAL_RESPONSE=$(curl -sf -X POST http://localhost:8000/evaluate \
        -H "Content-Type: application/json" \
        -d '{"model": "test-model", "base_url": "http://localhost:9999/act", "task_id": "autobooks-demo-task-1", "max_steps": 1}' 2>&1 || true)

    log_info "Evaluate response: ${EVAL_RESPONSE}"
    log_success "Endpoint test complete"
}

clean() {
    log_info "Cleaning up containers..."

    # Stop main container
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    # Stop sibling containers
    docker rm -f autoppia-web-autobooks 2>/dev/null || true
    docker rm -f autoppia-webs-server 2>/dev/null || true
    docker rm -f autoppia-webs-postgres 2>/dev/null || true

    # Remove network
    docker network rm autoppia-net 2>/dev/null || true

    log_success "Cleanup complete"
}

logs() {
    log_info "Showing container logs..."
    docker logs -f "${CONTAINER_NAME}"
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build   - Build the Docker image"
    echo "  run     - Run the container"
    echo "  test    - Test the /evaluate endpoint"
    echo "  clean   - Stop and remove all autoppia containers"
    echo "  logs    - Show container logs"
    echo "  all     - Build, run, and test (default)"
    echo ""
}

# Main
case "${1:-all}" in
    build)
        build
        ;;
    run)
        run
        ;;
    test)
        test_endpoint
        ;;
    clean)
        clean
        ;;
    logs)
        logs
        ;;
    all)
        build
        run
        test_endpoint
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
