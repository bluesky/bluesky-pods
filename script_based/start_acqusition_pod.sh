#! /usr/bin/bash
set -e
set -o xtrace

IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | head -n 1`

###########################################################################################
# Main acquisition services with adaptive etc
# Separate out databroker server, kafka consumer that only use main pod via kafka topic

# create the acquisition pod
podman pod create -n acquisition  -p 9092:9092/tcp -p 60610:9090/tcp
# just to get minimal IOC running
podman run -dt --pod acquisition --rm caproto

podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.mini_beamline -v
podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.random_walk -v
podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.random_walk -v  --prefix="random_walk:horiz-"
podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.random_walk -v  --prefix="random_walk:vert-"
podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.simple -v
podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.thermo_sim -v
podman run -dt --pod acquisition --init --rm caproto python3 -m caproto.ioc_examples.trigger_with_pc -v

# start up a mongo
podman run -dt --pod acquisition --rm docker.io/library/mongo:latest
# start up a zmq proxy
podman run --pod acquisition -dt --rm  bluesky bluesky-0MQ-proxy 4567 5678
# set up kafka + zookeeper
podman run --pod acquisition \
       -dt --rm \
       -e ALLOW_ANONYMOUS_LOGIN=yes \
       -v /bitnami \
       docker.io/bitnami/zookeeper:3

# The listeners still need some work
# https://www.confluent.io/blog/kafka-client-cannot-connect-to-broker-on-aws-on-docker-etc/
# https://www.confluent.io/blog/kafka-listeners-explained/
# https://github.com/rmoff/kafka-listeners
podman run --pod acquisition \
       -dt --rm \
       --name=acq_kafka \
       -e KAFKA_CFG_ZOOKEEPER_CONNECT=localhost:2181   \
       -e ALLOW_PLAINTEXT_LISTENER=yes \
       -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT \
       -e KAFKA_CFG_LISTENERS=PLAINTEXT://:29092,PLAINTEXT_HOST://:9092  \
       -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:29092,PLAINTEXT_HOST://$IP_ADDR:9092 \
       -e KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true \
       -v /bitnami \
       docker.io/bitnami/kafka:2
# make sure kafka is alive
sleep 2
# create the topic we are going to publish to
podman exec acq_kafka kafka-topics.sh --create --topic mad.bluesky.documents --bootstrap-server localhost:29092


# set up insert into mongo via kafka
podman run --pod acquisition\
       -dt --rm \
       -v `pwd`/../bluesky_config/scripts:'/app' \
       -w '/app' \
       --name=acq_mongo_consumer \
       bluesky \
       python3 mongo_consumer.py  \
           --kafka_server=localhost:29092 --kafka_group=acq_local_consumers

# start up redis
podman run -dt --pod acquisition  --rm docker.io/redis

# start up queueserver manager
podman run --pod acquisition \
       -td --rm \
       --name=acq_queue_manager \
       bluesky \
       start-re-manager --kafka_topic=mad.bluesky.documents --kafka_server=localhost:29092

# start up queueserver webserver
podman run --pod acquisition \
       -td --rm \
       --name=acq_queue_server \
       bluesky \
       uvicorn bluesky_queueserver.server.server:app --host localhost --port 8081


CLIENT_DIR=../bluesky-webclient

if [ ! -d $CLIENT_DIR ]; then
    NGINX_CONTAINER=bluesky-webclient
else
    pushd $CLIENT_DIR
    podman run --rm -v .:/src -w /src node:15.0.1-buster bash -c 'npm install && npm run build'
    popd
    MOUNT="-v $CLIENT_DIR/build:/var/www/html:ro"
    NGINX_CONTAINER=docker.io/nginx
fi

# start nginx
podman run --pod acquisition \
       -v ../bluesky_config/nginx/acqusition.conf:/etc/nginx/nginx.conf:ro \
       $MOUNT \
       --name=acq_reverse_proxy \
       -dt --rm \
       $NGINX_CONTAINER


bash start_ad.sh MADSIM1
