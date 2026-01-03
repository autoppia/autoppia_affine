# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies (git, curl, Playwright browser deps, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git curl \
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
    rm -rf /var/lib/apt/lists/*

# Copy only essential pieces from the monorepo:
#  - autoppia_affine code (package + src)
#  - Autobooks tasks JSON used by the evaluator
COPY autoppia_affine /app/autoppia_affine
COPY autoppia_affine/data/tasks/autoppia_books_tasks.json /app/data/tasks/autoppia_books_tasks.json

# Install minimal runtime dependencies:
#  - autoppia_iwa from GitHub main (for evaluator + demo webs)
#  - FastAPI stack and HTTP client
#  - Playwright browser and Chromium binary for StatefulEvaluator
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir "autoppia_iwa @ git+https://github.com/autoppia/autoppia_iwa.git@main" fastapi uvicorn httpx loguru && \
    playwright install chromium

# Make the autoppia_affine repo layout (under /app/autoppia_affine) the import root
# and configure autoppia_iwa demo webs to point at the externally running
# Autobooks deployment, mirroring your working host .env.
ENV PYTHONPATH=/app/autoppia_affine \
    DEMO_WEBS_ENDPOINT="http://84.247.180.192" \
    DEMO_WEBS_STARTING_PORT=8000 \
    DEMO_WEB_SERVICE_PORT=8090 \
    VALIDATOR_ID="1" \
    EVALUATOR_HEADLESS=true
WORKDIR /app/autoppia_affine

EXPOSE 8000

CMD ["uvicorn", "autoppia_affine.src.affine_env.env:app", "--host", "0.0.0.0", "--port", "8000"]
