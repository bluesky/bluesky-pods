#! /usr/bin/bash
set -e
set -o xtrace

xhost +local:docker

podman run --pod adaptive -ti -v /tmp/.X11-unix/:/tmp/.X11-unix/ -e DISPLAY -v `pwd`:'/app' -w '/app' -v ./bluesky_config/ipython:/etc/ipython  --rm bluesky ipython3 --ipython-dir=/etc/ipython
