podman run -dt --rm -p 6977:6669 databroker-server uvicorn --port 6669 databroker_server.main:app
