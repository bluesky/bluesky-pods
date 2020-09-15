#! /usr/bin/bash
set -e
set -o xtrace

podman run --pod acquisition --rm -ti -v `pwd`/bluesky_config/scripts:'/app' -w '/app' bluesky python3 adaptive_consumer.py
