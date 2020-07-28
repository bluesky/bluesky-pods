#! /usr/bin/bash
set -e
set -o xtrace

# create the pod
podman pod create -n adaptive
# just to get minimal IOC running
podman run -dt --pod adaptive caproto
# start up a mongo
podman run -dt --pod adaptive mongo
# stort up redis
podman run -dt --pod adaptive redis
# start up a zmq proxy
podman run --pod adaptive -dt bluesky bluesky-0MQ-proxy 4567 5678
