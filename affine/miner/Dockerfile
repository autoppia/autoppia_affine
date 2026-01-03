FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build context is the monorepo root; copy only the autoppia_affine repo to /app
COPY autoppia_affine /app/autoppia_affine

# Install minimal dependencies for the miner API
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx

EXPOSE 9000

# Miner app lives at /app/autoppia_affine/affine/miner/app.py
ENV PYTHONPATH=/app/autoppia_affine
WORKDIR /app/autoppia_affine

CMD ["uvicorn", "affine.miner.app:app", "--host", "0.0.0.0", "--port", "9000"]
