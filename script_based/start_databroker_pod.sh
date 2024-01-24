#! /usr/bin/bash
set -e
set -o xtrace

IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p'`

########################################################################################################################
# Dataaccess pod.
podman pod create -n databroker -p 6942:9090/tcp -p 9999:8888/tcp
# start up a mongo
podman run -dt --pod databroker --rm mongo
# listen to kafka published from the other pod
podman run --pod databroker \
       -dt --rm \
       -v `pwd`/../bluesky_config/scripts:'/app' \
       -w '/app' \
       --name=db_mongo_consumer \
       bluesky \
       python3 mongo_consumer.py --kafka_server=$IP_ADDR:9092

# start the databroker server
podman run --pod databroker \
       --rm -dt \
       --name=db_server \
       -v ../bluesky_config/databroker:/usr/local/share/intake \
       -v ../papermill_templates:/usr/local/share/databroker_server/papermill_templates:ro \
       -e DATABROKER_SERVER_INTERNAL_JUPYTER_BASE_URL=http://localhost:8888 \
       -e DATABROKER_SERVER_EXTERNAL_JUPYTER_BASE_URL=http://localhost:9999 \
       -e DATABROKER_SERVER_JUPYTER_ACCESS_TOKEN=dev \
       -e DATABROKER_SERVER_JUPYTER_PAPERMILL_TEMPLATE=/usr/local/share/databroker_server/papermill_templates/dashboard_template.ipynb \
       databroker-server \
       uvicorn --port 8081 databroker_server.main:app

CLIENT_DIR=../databroker-client

if [ ! -d $CLIENT_DIR ]; then
    NGINX_CONTAINER=databroker-client
else
    pushd $CLIENT_DIR
    podman run --rm -v .:/src -w /src node:15.0.1-buster bash -c 'npm install && npm run build'
    popd
    MOUNT="-v $CLIENT_DIR/build:/var/www/html:ro"
    NGINX_CONTAINER=nginx
fi


# start nginx
podman run --pod databroker \
       -v ../bluesky_config/nginx/databroker.conf:/etc/nginx/nginx.conf:ro \
       $MOUNT \
       --name=db_reverse_proxy \
       -dt --rm \
       $NGINX_CONTAINER

podman run -dt --pod databroker --rm \
    -v ../bluesky_config/databroker:/usr/local/share/intake \
    quay.io/jupyter/scipy-notebook
