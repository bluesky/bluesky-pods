#! /usr/bin/bash
set -e
set -o xtrace


########################################################################################################################
# Dataaccess pod.
podman pod create -n databroker -p 6977:6669/tcp
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
podman run -dt --pod databroker --rm databroker-server uvicorn --port 6669 databroker_server.main:app
