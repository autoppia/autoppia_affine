# Autoppia Affine

Evaluation environment for web agents using the Autoppia IWA benchmark.

## Quick Start

```bash
# Build and start everything
./startup.sh all

# Run test (expects score 1.0)
python3 test.py

# Stop everything
./startup.sh stop
```

## Commands

```bash
./startup.sh build    # Build Docker images
./startup.sh start    # Start containers
./startup.sh stop     # Stop and cleanup
./startup.sh restart  # Stop + start
./startup.sh all      # Build + start
./startup.sh status   # Show container status
./startup.sh logs     # Follow env container logs
```

## API

### Health Check
```bash
curl http://localhost:8000/health
```

### Evaluate
```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "my-model",
    "base_url": "http://autoppia-affine-model:9000/act"
  }'
```

**Request:**
| Field | Required | Description |
|-------|----------|-------------|
| `model` | yes | Model name |
| `base_url` | yes | Full URL of model's `/act` endpoint |
| `task_id` | no | Specific task to evaluate |
| `max_steps` | no | Max steps per task (default: 30) |

**Response:**
```json
{
  "environment": "autoppia_affine_env",
  "total_score": 1.0,
  "success_rate": 1.0,
  "evaluated": 1,
  "details": [{"task_id": "...", "score": 1.0, "success": true, ...}]
}
```

## Affinetes Integration

```python
import affinetes as af

env = af.load_env(
    image="autoppia-affine-env:latest",
    mode="docker",
    env_vars={"CHUTES_API_KEY": api_key},
    force_recreate=True,
    cleanup=False,
    # Mount Docker socket for DOOD (Docker-out-of-Docker)
    volumes={
        "/var/run/docker.sock": {
            "bind": "/var/run/docker.sock",
            "mode": "rw",
        }
    },
)

result = await env.evaluate(
    model="my-model",
    base_url="http://my-miner:9000/act",
)
```

## Project Structure

```
autoppia_affine/
├── startup.sh              # Build/run/stop script
├── test.py                 # Simple test script
├── env.py                  # FastAPI /evaluate endpoint
├── utils.py                # Task loading
├── Dockerfile              # Main container
├── docker-compose.webs.yml # Demo websites
├── entrypoint.sh           # Container startup
├── data/
│   └── autoppia_books_tasks.json
└── model/
    ├── app.py              # Reference test model
    └── Dockerfile
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUTES_API_KEY` | - | API key for Chutes LLM provider |
| `AUTOPPIA_AFFINE_MAX_STEPS` | 30 | Max steps per task |

## Troubleshooting

```bash
# Check container status
docker ps --filter "name=autoppia-"

# View logs
docker logs autoppia-affine-env

# Test connectivity inside container
docker exec autoppia-affine-env curl http://localhost:8001
docker exec autoppia-affine-env curl http://localhost:8080/health
```
