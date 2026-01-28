#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONOREPO_ROOT="${SCRIPT_DIR}/.."

ENV_IMAGE="autoppia-affine-env:latest"
ENV_CONTAINER="autoppia-affine-env"
MODEL_IMAGE="autoppia-affine-model:latest"
MODEL_CONTAINER="autoppia-affine-model"
NETWORK="autoppia-net"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[startup]${NC} $1"; }
ok() { echo -e "${GREEN}[startup]${NC} $1"; }
err() { echo -e "${RED}[startup]${NC} $1"; }

cleanup() {
    log "Stopping containers..."
    docker rm -f "${ENV_CONTAINER}" "${MODEL_CONTAINER}" 2>/dev/null || true
    docker rm -f autoppia-web-autobooks autoppia-webs-server autoppia-webs-postgres 2>/dev/null || true
    docker network rm "${NETWORK}" 2>/dev/null || true
    ok "Cleanup complete"
}

build() {
    log "Building env image..."
    docker build -t "${ENV_IMAGE}" -f "${SCRIPT_DIR}/Dockerfile" "${MONOREPO_ROOT}"

    log "Building model image..."
    docker build -t "${MODEL_IMAGE}" -f "${SCRIPT_DIR}/model/Dockerfile" "${SCRIPT_DIR}"

    ok "Images built"
}

start() {
    log "Creating network..."
    docker network create "${NETWORK}" 2>/dev/null || true

    log "Starting env container..."
    docker rm -f "${ENV_CONTAINER}" 2>/dev/null || true
    docker run -d \
        --name "${ENV_CONTAINER}" \
        --network "${NETWORK}" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -p 8000:8000 \
        "${ENV_IMAGE}"

    log "Starting model container..."
    docker rm -f "${MODEL_CONTAINER}" 2>/dev/null || true
    docker run -d \
        --name "${MODEL_CONTAINER}" \
        --network "${NETWORK}" \
        -e CHUTES_API_KEY="${CHUTES_API_KEY:-}" \
        "${MODEL_IMAGE}"

    log "Waiting for env to be ready (this may take 1-2 minutes)..."
    for i in {1..120}; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            ok "Env ready at http://localhost:8000"
            return 0
        fi
        sleep 2
    done

    err "Timeout waiting for env"
    docker logs "${ENV_CONTAINER}" --tail 50
    exit 1
}

status() {
    echo ""
    log "Container status:"
    docker ps --filter "name=autoppia-" --format "table {{.Names}}\t{{.Status}}"
    echo ""
}

case "${1:-start}" in
    build)
        build
        ;;
    start)
        start
        status
        ;;
    stop|clean)
        cleanup
        ;;
    restart)
        cleanup
        start
        status
        ;;
    all)
        build
        start
        status
        ;;
    status)
        status
        ;;
    logs)
        docker logs -f "${ENV_CONTAINER}"
        ;;
    *)
        echo "Usage: $0 [build|start|stop|restart|all|status|logs]"
        exit 1
        ;;
esac
