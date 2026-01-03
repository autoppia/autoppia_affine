#!/usr/bin/env bash
set -euo pipefail

# Build and run the hardcoded miner container that exposes /act.

IMAGE_NAME="autoppia-affine-miner:latest"
CONTAINER_NAME="autoppia-affine-miner"
NETWORK_NAME="autoppia-affine-net"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[miner] Using build context root: ${ROOT_DIR}"
cd "${ROOT_DIR}"

if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}\$"; then
  echo "[miner] Creating Docker network ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
fi

echo "[miner] Building image ${IMAGE_NAME}"
docker build \
  -f autoppia_affine/affine/miner/Dockerfile \
  -t "${IMAGE_NAME}" \
  "${ROOT_DIR}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "[miner] Removing existing container ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

echo "[miner] Starting container ${CONTAINER_NAME} on network ${NETWORK_NAME}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  --network "${NETWORK_NAME}" \
  "${IMAGE_NAME}"

echo "[miner] Container running inside Docker network ${NETWORK_NAME} (no host port binding)."
