#! /usr/bin/bash
set -e
set -o xtrace

# This was a useful reference for the $DISPLAY and xauth stuff.
# https://stackoverflow.com/a/48235281/1221924

if [ -v "SSH_CONNECTION" ]; then
	echo "SSH_CONNECTION is set"
	# Unlike the recommendation in the linked SO post,
	# we are not using docker and thus not using docker's special network.
	# Instead, we use the IP of the host.
	IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | head -n 1`
	DISPLAY=`echo $DISPLAY | sed "s/^[^:]*\(.*\)/${IP_ADDR}\1/"`
fi
XAUTH=/tmp/.docker.xauth
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f $XAUTH nmerge -

# https://stackoverflow.com/questions/24112727/relative-paths-based-on-file-location-instead-of-current-working-directory
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

if [ "$1" != "" ]; then
    imagename=$1
else
    imagename="bluesky"
fi

podman run --pod acquisition \
       -ti  --rm \
       -v /tmp/.X11-unix/:/tmp/.X11-unix/ \
       -e DISPLAY \
       -v $XAUTH:$XAUTH \
       -e XAUTHORITY=$XAUTH \
       -v `pwd`:'/app' -w '/app' \
       -e XDG_RUNTIME_DIR=/tmp/runtime-$USER \
       -e EPICS_CA_ADDR_LIST=10.0.2.255 \
       -e EPICS_CA_AUTO_ADDR_LIST=no \
       $imagename \
       bash
