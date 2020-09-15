#! /usr/bin/bash
set -e
set -o xtrace


########################################################################################################################
# Dataaccess pod.
podman pod create -n databroker -p 6977:9090/tcp
# start up a mongo
podman run -dt --pod databroker --rm mongo
# listen to kafka published from the other pod
podman run --pod databroker \
       -dt --rm \
       -v `pwd`/bluesky_config/scripts:'/app' \
       -w '/app' \
       bluesky \
       python3 mongo_consumer.py

# start the databroker server
podman run -dt --pod databroker --rm databroker-server uvicorn --port 8081 databroker_server.main:app


# start nginx
podman run --pod databroker \
       -v ./bluesky_config/nginx/databroker.conf:/etc/nginx/nginx.conf:ro \
       -v ./bluesky_config/static_web/databroker:/var/www/html:ro \
       -d --rm \
       nginx
