#! /usr/bin/bash
set -e
set -o xtrace

# create the pod
podman pod create -n adaptive
# just to get minimal IOC running
podman run -dt --pod adaptive --rm caproto
# start up a mongo
podman run -dt --pod adaptive --rm mongo
# stort up redis
podman run -dt --pod adaptive  --rm redis
# start up a zmq proxy
podman run --pod adaptive -dt --rm  bluesky bluesky-0MQ-proxy 4567 5678

# set up kafka
podman run --pod adaptive -dt -e ALLOW_ANONYMOUS_LOGIN=yes -v /bitnami  --rm bitnami/zookeeper:3

podman run --pod adaptive -dt --rm  -e KAFKA_CFG_ZOOKEEPER_CONNECT=localhost:2181      -e ALLOW_PLAINTEXT_LISTENER=yes      -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT      -e KAFKA_CFG_LISTENERS=PLAINTEXT://:29092,PLAINTEXT_HOST://:9092      -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:29092,PLAINTEXT_HOST://localhost:9092      -e KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true -v /bitnami bitnami/kafka:2

# start up queueserver
podman run --pod adaptive -td --rm  bluesky python3 -m aiohttp.web -H 0.0.0.0 -P 8081 bluesky_queueserver.server:init_func
