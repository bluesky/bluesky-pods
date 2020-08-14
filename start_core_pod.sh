#! /usr/bin/bash
set -e
set -o xtrace

# Main acquisition services with adaptive etc
# Separate out databroker server, kafka consumer that only use main pod via kafka topic

# create the acquisition pod
podman pod create -n acquisition -p 60606:8081/tcp -p 9092:9092/tcp -p 29092:29092/tcp
# just to get minimal IOC running
podman run -dt --pod acquisition --rm caproto

podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.mini_beamline -v --interfaces=127.0.0.1
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.random_walk -v --interfaces=127.0.0.1
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.random_walk -v --interfaces=127.0.0.1 --prefix="random_walk:horiz-"
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.random_walk -v --interfaces=127.0.0.1 --prefix="random_walk:vert-"
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.simple -v --interfaces=127.0.0.1
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.thermo_sim -v --interfaces=127.0.0.1
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.trigger_with_pc -v --interfaces=127.0.0.1

# start up a mongo
podman run -dt --pod acquisition --rm mongo
# stort up redis
podman run -dt --pod acquisition  --rm redis
# start up a zmq proxy
podman run --pod acquisition -dt --rm  bluesky bluesky-0MQ-proxy 4567 5678

# set up kafka
podman run --pod acquisition -dt -e ALLOW_ANONYMOUS_LOGIN=yes -v /bitnami  --rm bitnami/zookeeper:3

podman run --pod acquisition \
       -dt --rm \
       -e KAFKA_CFG_ZOOKEEPER_CONNECT=localhost:2181   \
       -e ALLOW_PLAINTEXT_LISTENER=yes \
       -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT \
       -e KAFKA_CFG_LISTENERS=PLAINTEXT://:29092,PLAINTEXT_HOST://:9092  \
       -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:29092,PLAINTEXT_HOST://localhost:9092 \
       -e KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true \
       -v /bitnami \
       bitnami/kafka:2

# start up queueserver
podman run --pod acquisition -td --rm bluesky python3 -m aiohttp.web -H localhost -P 8081 bluesky_queueserver.server:init_func

# start up databroker server
podman pod create -n databroker -p 6977:6669/tcp
# start up a mongo
podman run -dt --pod databroker --rm mongo
podman run --pod databroker -dt --rm databroker-server uvicorn --port 6669 databroker_server.main:app
