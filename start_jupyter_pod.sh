#! /usr/bin/bash
set -e
set -o xtrace

podman pod create -n jupyter -p 8888:8888/tcp
podman run -dt --pod jupyter --rm jupyter
