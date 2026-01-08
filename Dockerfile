# =============================================================================
# Autoppia Affine Environment - Self-Contained Docker Image
# =============================================================================
# This image contains:
# - FastAPI /evaluate endpoint
# - autoppia_iwa evaluation framework
# - Playwright + Chromium for browser automation
# - Docker CLI for DOOD (Docker-out-of-Docker) pattern
# - Pre-cloned demo websites repository
#
# Usage:
#   docker build -t autoppia-affine-env -f Dockerfile ..
#   docker run -v /var/run/docker.sock:/var/run/docker.sock -p 8000:8000 autoppia-affine-env
# =============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# =============================================================================
# Install system dependencies + Docker CLI
# =============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Build tools and utilities
        git curl wget ca-certificates gnupg \
        # Port forwarding (for routing localhost to Docker containers)
        socat \
        # Playwright/Chromium dependencies
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdrm2 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libxcb1 \
        libxkbcommon0 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 && \
    # Install Docker CLI (for DOOD pattern)
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin && \
    # Cleanup
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# Clone demo websites repository
# =============================================================================
RUN git clone --depth 1 https://github.com/autoppia/autoppia_webs_demo.git /app/webs_demo

# =============================================================================
# Copy autoppia_iwa and affine env code
# Build context is the monorepo root
# =============================================================================
COPY autoppia_iwa /app/autoppia_iwa
COPY autoppia_affine/env.py /app/env.py
COPY autoppia_affine/utils.py /app/utils.py
COPY autoppia_affine/data/autoppia_books_tasks.json /app/data/autoppia_books_tasks.json
COPY autoppia_affine/docker-compose.webs.yml /app/docker-compose.webs.yml
COPY autoppia_affine/entrypoint.sh /app/entrypoint.sh

# =============================================================================
# Install Python dependencies
# =============================================================================
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/autoppia_iwa/requirements.txt fastapi uvicorn loguru httpx && \
    playwright install chromium && \
    printf 'EVALUATOR_HEADLESS=true\n' > /app/autoppia_iwa/.env

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# =============================================================================
# Environment configuration
# =============================================================================
# DEMO_WEBS_ENDPOINT: Base URL for demo websites (Docker network name)
# The evaluator constructs full URLs like: {DEMO_WEBS_ENDPOINT}:{port}{path}
#
# For autobooks (web_2), port is 8001, so URLs become:
#   http://autoppia-web-autobooks:8001/
#
# Note: The StatefulEvaluator in autoppia_iwa uses web_project_id to determine
# which demo web to connect to. The mapping is handled via DEMO_WEBS_ENDPOINT.
# =============================================================================
ENV PYTHONPATH=/app/autoppia_iwa \
    # Use localhost - port forwarding routes to Docker containers
    # socat forwards: localhost:8001 → autoppia-web-autobooks:8001
    #                 localhost:8080 → autoppia-webs-server:8080
    DEMO_WEBS_ENDPOINT="http://localhost" \
    DEMO_WEBS_STARTING_PORT=8000 \
    DEMO_WEB_SERVICE_PORT=8080 \
    VALIDATOR_ID="1" \
    EVALUATOR_HEADLESS=true

WORKDIR /app

EXPOSE 8000

# Use entrypoint script to start demo webs first, then FastAPI
ENTRYPOINT ["/app/entrypoint.sh"]
