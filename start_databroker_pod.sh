#! /usr/bin/bash
set -e
set -o xtrace

IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p'`

########################################################################################################################
# Dataaccess pod.
podman pod create -n databroker -p 6942:9090/tcp
# start up a mongo
podman run -dt --pod databroker --rm mongo
# listen to kafka published from the other pod
podman run --pod databroker \
       -dt --rm \
       -v `pwd`/bluesky_config/scripts:'/app' \
       -w '/app' \
       --name=db_mongo_consumer \
       bluesky \
       python3 mongo_consumer.py --kafka_server=$IP_ADDR:9092

# start the databroker server
podman run --pod databroker \
       --rm -dt \
       --name=db_server \
       -v ./bluesky_config/databroker:/usr/local/share/intake \
       databroker-server \
       uvicorn --port 8081 databroker_server.main:app


# start nginx
podman run --pod databroker \
       -v ./bluesky_config/nginx/databroker.conf:/etc/nginx/nginx.conf:ro \
       -v ./bluesky_config/static_web/databroker:/var/www/html:ro \
       -d --rm \
       nginx
