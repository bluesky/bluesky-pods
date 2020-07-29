#! /usr/bin/bash
set -e
set -o xtrace

# create the pod
podman pod create -n adaptive
# just to get minimal IOC running
podman run -dt --pod adaptive --rm caproto
# start up a mongo
podman run -dt --pod adaptive --rm mongo
# stort up redis
podman run -dt --pod adaptive  --rm redis
# start up a zmq proxy
podman run --pod adaptive -dt --rm  bluesky bluesky-0MQ-proxy 4567 5678
