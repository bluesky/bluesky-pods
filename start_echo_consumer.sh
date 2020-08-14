#! /usr/bin/bash
set -e
set -o xtrace

podman run --pod acquisition --rm -ti -v `pwd`:'/app' -w '/app' bluesky python3 echo_consumer.py
