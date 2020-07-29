#! /usr/bin/bash
set -e
set -o xtrace

xhost +local:docker

podman run --pod adaptive -ti -v /tmp/.X11-unix/:/tmp/.X11-unix/ -e DISPLAY -v `pwd`:'/app' -w '/app' --rm bluesky ipython3 -i fake_profile.py
