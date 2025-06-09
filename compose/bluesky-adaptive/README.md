# Bluesky Adaptive Agents

## File contents

- `reactive_random_walk.py`: a simpple reactive random walk agent that can be used to test the full stack in the acq-pod.
- `mock_agent.py`: a mock agent that can be used in isolation to build against adaptive. This can be used with Tiled or without by setting the `USE_TILED` environment variable.

## Running the mock agent in isolation

Navigating to this directory and running the following command will start the mock agent in a container.
The agent will be available at `http://localhost:8000`, with the swagger UI at `http://localhost:8000/docs`.
It will not be particularly interactive, but it will respond to requests and can be used to test UI communication.

```bash
cd compose/bluesky-adaptive
podman run --rm \
    -v $(pwd):/src/bluesky-adaptive \
    -e BS_AGENT_STARTUP_SCRIPT_PATH=/src/bluesky-adaptive/mock_agent.py \
    -e USE_TILED=0 \
    -p 8000:8000 \
    bluesky:latest \
    uvicorn bluesky_adaptive.server:app --host 0.0.0.0 --port 8000
```

## Running the mock agent without experiment orchestration

To run the mock agent with only a tiled server and database (to write state/reports to), you can use the compose file in this directory.

```bash
cd compose/bluesky-adaptive
podman-compose -f compose.yaml up -d
```

This will start the tiled server and database, and the mock agent will be available at `http://localhost:8000` with the swagger UI at `http://localhost:8000/docs`.
