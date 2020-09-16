#! /usr/bin/bash

# This is adapted from https://github.com/prjemian/epics-docker/blob/master/n4_areaDetector/start_adsim.sh
# by Pete Jemian

set -e
set -o xtrace


PRE=${1:-13SIM1}

# -------------------------------------------
# IOC prefix
PREFIX=${PRE}:
# name of docker container
CONTAINER=ioc${PRE}
# name of docker image
SHORT_NAME=synapps-6.1-ad-3.7
IMAGE=prjemian/${SHORT_NAME}:latest
# name of IOC manager (start, stop, status, ...)
IOC_MANAGER=iocSimDetector/simDetector.sh
# container will quit unless it has something to run
# this is trivial but shows that container is running
# prints date/time every 10 seconds
KEEP_ALIVE_COMMAND="while true; do date; sleep 10; done"
# pass the IOC PREFIX to the container at boot time
ENVIRONMENT="AD_PREFIX=${PREFIX}"
# convenience definitions
RUN="docker exec ${CONTAINER}"
DATA_ROOT=`pwd`/volumes/data
TMP_ROOT=`pwd`/volumes/tmp
HOST_IOC_ROOT=${TMP_ROOT}/${CONTAINER}
# -------------------------------------------
mkdir -p ${TMP_ROOT}
mkdir -p ${DATA_ROOT}
echo -n "starting container ${CONTAINER} ... "
podman run --pod=acquisition \
       -d --rm \
       --name ${CONTAINER} \
       -e "${ENVIRONMENT}" \
       -v "${TMP_ROOT}":/tmp \
       -v "${DATA_ROOT}":/data \
       ${IMAGE} bash -c  "${KEEP_ALIVE_COMMAND}"

sleep 1

podman exec ${CONTAINER} ${IOC_MANAGER} start
