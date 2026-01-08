# Autoppia Affine

Affine-compatible evaluation harness for the Autoppia IWA web-agent benchmark.

This repo provides a **self-contained** Docker environment that Affine can use to evaluate web agents. It exposes a single `/evaluate` HTTP endpoint that an Affine validator calls, pointing it to a miner/model URL. Under the hood it runs the real Autoppia IWA benchmark (`StatefulEvaluator`) against that model.

## Architecture

The environment uses the **DOOD (Docker-out-of-Docker)** pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│  Host Docker Daemon (via /var/run/docker.sock)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │ autoppia-affine-env │    │ Sibling Containers              │ │
│  │ (main container)    │    │                                 │ │
│  │                     │    │  - autoppia-webs-server:8080    │ │
│  │  - FastAPI :8000    │◄──►│  - autoppia-webs-postgres       │ │
│  │  - Port forwarding  │    │  - autoppia-web-autobooks:8001  │ │
│  │  - Playwright       │    │                                 │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
│                                                                 │
│  Network: autoppia-net (internal, isolated)                     │
└─────────────────────────────────────────────────────────────────┘
```

**Key features:**
- All demo websites run as sibling containers (not nested)
- Port forwarding via `socat` routes localhost → Docker containers
- Network isolation: websites only accessible within Docker network
- Main container exposes only port 8000 to host

## Quick Start

### Prerequisites

- Docker installed and running
- Docker socket accessible at `/var/run/docker.sock`

### Build and Run

```bash
# Clone if needed
cd autoppia_affine

# One-command build, run, and test
./test_local.sh all

# Or step by step:
./test_local.sh build   # Build the Docker image
./test_local.sh run     # Start the container
./test_local.sh test    # Test the endpoints
./test_local.sh clean   # Cleanup all containers
```

### Manual Docker Commands

```bash
# Build from monorepo root
docker build -t autoppia-affine-env -f autoppia_affine/Dockerfile .

# Run with Docker socket mounted
docker run -d \
  --name autoppia-affine-env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 8000:8000 \
  autoppia-affine-env

# Check logs
docker logs -f autoppia-affine-env

# Test health endpoint
curl http://localhost:8000/health

# Cleanup
docker rm -f autoppia-affine-env autoppia-web-autobooks autoppia-webs-server autoppia-webs-postgres
docker network rm autoppia-net
```

## How `/evaluate` Works

1. **Load tasks** from `data/autoppia_books_tasks.json`
2. **Set up evaluator** - create `StatefulEvaluator` per task
3. **Step the model** - for each step (up to `max_steps`):
   - Send current state (URL, HTML) to miner's `/act` endpoint
   - Execute returned actions via browser
   - Check if task completed
4. **Return metrics** - total score, success rate, per-task details

### Request Format

```json
POST /evaluate
{
  "model": "your-model-name",
  "base_url": "http://your-miner:9000/act",
  "task_id": "autobooks-demo-task-1",  // optional
  "max_steps": 30  // optional
}
```

### Response Format

```json
{
  "environment": "autoppia_affine_env",
  "total_score": 1.0,
  "success_rate": 1.0,
  "evaluated": 1,
  "details": [{
    "task_id": "autobooks-demo-task-1",
    "project_id": "autobooks",
    "score": 1.0,
    "raw_score": 1.0,
    "success": true,
    "tests_passed": 1,
    "total_tests": 1,
    "steps": 1
  }]
}
```

## File Structure

```
autoppia_affine/
├── Dockerfile                    # Main container (self-contained)
├── entrypoint.sh                 # Startup script (spawns demo webs)
├── docker-compose.webs.yml       # Demo website containers
├── env.py                        # FastAPI /evaluate endpoint
├── utils.py                      # Task loading utilities
├── test_local.sh                 # Local testing script
├── data/
│   └── autoppia_books_tasks.json # Demo tasks
├── model/                        # Reference model (for testing)
│   ├── app.py
│   ├── Dockerfile
│   └── build_and_run_model.sh
└── README.md
```

## Adding More Websites

To add more demo websites, edit `docker-compose.webs.yml`:

1. Uncomment/add a new service following the template
2. Add a port forward in `entrypoint.sh`:
   ```bash
   socat TCP-LISTEN:8000,fork,reuseaddr TCP:autoppia-web-autocinema:8000 &
   ```
3. Rebuild the image

## Network Isolation

- Demo websites are only accessible within the `autoppia-net` Docker network
- Port forwarding routes `localhost:800X` → `container:800X` inside main container
- Only port 8000 (FastAPI) is exposed to the host
- External access to demo websites is not possible

## Affinetes Integration

For Affinetes URL mode:

```python
import affinetes as af

env = af.load_env(
    image="autoppia-affine-env:latest",
    mode="docker",
    env_vars={"CHUTES_API_KEY": api_key},
    volumes={
        "/var/run/docker.sock": {
            "bind": "/var/run/docker.sock",
            "mode": "rw"
        }
    },
)

result = env.evaluate(
    model="your-model",
    base_url="http://your-miner/act",
)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_WEBS_ENDPOINT` | `http://localhost` | Base URL for demo websites |
| `DEMO_WEBS_STARTING_PORT` | `8000` | Starting port for websites |
| `DEMO_WEB_SERVICE_PORT` | `8080` | webs-server port |
| `EVALUATOR_HEADLESS` | `true` | Run browser headless |
| `AUTOPPIA_AFFINE_MAX_STEPS` | `30` | Default max steps per task |

## Troubleshooting

### Container won't start
```bash
# Check if Docker socket is accessible
docker info

# Check container logs
docker logs autoppia-affine-env
```

### Demo websites not responding
```bash
# Check sibling containers
docker ps --filter "name=autoppia-"

# Check network
docker network inspect autoppia-net
```

### Port forwarding issues
```bash
# Inside the container, test connectivity
docker exec autoppia-affine-env curl http://localhost:8001
docker exec autoppia-affine-env curl http://localhost:8080/health
```
