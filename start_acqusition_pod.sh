#! /usr/bin/bash
set -e
set -o xtrace

########################################################################################################################
# Main acquisition services with adaptive etc
# Separate out databroker server, kafka consumer that only use main pod via kafka topic

# create the acquisition pod
podman pod create -n acquisition  -p 9092:9092/tcp -p 29092:29092/tcp -p 60607:9090/tcp
# just to get minimal IOC running
podman run -dt --pod acquisition --rm caproto

podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.mini_beamline -v
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.random_walk -v
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.random_walk -v  --prefix="random_walk:horiz-"
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.random_walk -v  --prefix="random_walk:vert-"
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.simple -v
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.thermo_sim -v
podman run -dt --pod acquisition --rm caproto python3 -m caproto.ioc_examples.trigger_with_pc -v

# start up a mongo
podman run -dt --pod acquisition --rm mongo
# start up a zmq proxy
podman run --pod acquisition -dt --rm  bluesky bluesky-0MQ-proxy 4567 5678
# set up kafka + zookeeper
podman run --pod acquisition \
       -dt --rm \
       -e ALLOW_ANONYMOUS_LOGIN=yes \
       -v /bitnami \
       bitnami/zookeeper:3
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

# set up insert into mongo via kafka
podman run --pod acquisition\
       -dt --rm \
       -v `pwd`/bluesky_config/scripts:'/app' \
       -w '/app' \
       bluesky \
       python3 mongo_consumer.py

# start up redis
podman run -dt --pod acquisition  --rm redis


# start up queueserver
podman run --pod acquisition -td --rm bluesky python3 -m aiohttp.web -H localhost -P 8081 bluesky_queueserver.server:init_func

# start nginx
podman run --pod acquisition \
       -v ./bluesky_config/nginx/acqusition.conf:/etc/nginx/nginx.conf:ro \
       -v ./bluesky_config/static_web/databroker:/var/www/html:ro \
       -d --rm \
       nginx
