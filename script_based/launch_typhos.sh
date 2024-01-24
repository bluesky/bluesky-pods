#! /usr/bin/bash
set -e
set -o xtrace

xhost +local:docker

podman run --pod acquisition \
       -ti  --rm \
       -v /tmp/.X11-unix/:/tmp/.X11-unix/ -e DISPLAY \
       -v `pwd`:'/app' -w '/app' \
       -v ./bluesky_config/ipython:/usr/local/share/ipython \
       -v ./bluesky_config/databroker:/usr/local/share/intake \
       -v ./bluesky_config/happi:/usr/local/share/happi \
       -e HAPPI_CFG=/usr/local/share/happi/happi.ini \
       -e PYTHONPATH=/usr/local/share/ipython \
       typhos \
       typhos pinhole motor_ph
