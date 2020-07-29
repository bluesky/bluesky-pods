#! /usr/bin/bash
set -e
set -o xtrace

podman run --pod adaptive --rm -ti -v `pwd`:'/app' -w '/app' bluesky python3 adaptive_consumer.py
