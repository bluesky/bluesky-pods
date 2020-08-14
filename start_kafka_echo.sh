#! /usr/bin/bash
set -e
set -o xtrace

podman run --pod acquisition -ti -v `pwd`:'/app' -w '/app' bluesky python3 kafka_echo_consumer.py
