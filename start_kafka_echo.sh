#! /usr/bin/bash
set -e
set -o xtrace

podman run --pod acquisition -ti -v `pwd`/bluesky_config/scripts:'/app' -w '/app' bluesky python3 kafka_echo_consumer.py
