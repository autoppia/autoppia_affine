#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="autoppia-affine-env:latest"
CONTAINER_NAME="autoppia-affine-env"
NETWORK_NAME="autoppia-affine-net"

# Build context root is the monorepo root (one level up from autoppia_affine)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[env] Using build context root: ${ROOT_DIR}"
cd "${ROOT_DIR}"

if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}\$"; then
  echo "[env] Creating Docker network ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
fi

echo "[env] Building image ${IMAGE_NAME}"
docker build \
  -f autoppia_affine/Dockerfile \
  -t "${IMAGE_NAME}" \
  "${ROOT_DIR}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "[env] Removing existing container ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

echo "[env] Starting container ${CONTAINER_NAME} on network ${NETWORK_NAME}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  --network "${NETWORK_NAME}" \
  -p 8002:8000 \
  "${IMAGE_NAME}"

echo "[env] Container running. Health check: curl http://localhost:8002/health"
