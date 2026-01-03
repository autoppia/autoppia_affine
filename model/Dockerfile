FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY autoppia_affine /app/autoppia_affine

RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx

EXPOSE 9000

ENV PYTHONPATH=/app/autoppia_affine
WORKDIR /app/autoppia_affine

CMD ["uvicorn", "model.app:app", "--host", "0.0.0.0", "--port", "9000"]
