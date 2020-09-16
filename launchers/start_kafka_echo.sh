#! /usr/bin/bash
set -e
set -o xtrace
IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p'`

podman run --pod databroker -ti -v `pwd`/bluesky_config/scripts:'/app' -w '/app' bluesky python3 kafka_echo_consumer.py  --kafka_server=$IP_ADDR:9092
