FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

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

# Build context is the monorepo root
# Copy the local autoppia_iwa repo and the affine env code
COPY autoppia_iwa /app/autoppia_iwa
COPY autoppia_affine/env.py /app/env.py
COPY autoppia_affine/utils.py /app/utils.py
COPY autoppia_affine/data/autoppia_books_tasks.json /app/data/autoppia_books_tasks.json

# Install dependencies from autoppia_iwa plus FastAPI and uvicorn,
# and force the evaluator to run headless by overriding the autoppia_iwa .env.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/autoppia_iwa/requirements.txt fastapi uvicorn loguru && \
    playwright install chromium && \
    printf 'EVALUATOR_HEADLESS=true\n' > /app/autoppia_iwa/.env

# Make the local autoppia_iwa repo importable.
# Point demo webs endpoint at the Autobooks frontend host:port used in the task.
ENV PYTHONPATH=/app/autoppia_iwa \
    DEMO_WEBS_ENDPOINT="http://84.247.180.192" \
    DEMO_WEBS_STARTING_PORT=8000 \
    DEMO_WEB_SERVICE_PORT=8090 \
    VALIDATOR_ID="1" \
    EVALUATOR_HEADLESS=true

WORKDIR /app

EXPOSE 8000

CMD ["uvicorn", "env:app", "--host", "0.0.0.0", "--port", "8000"]
