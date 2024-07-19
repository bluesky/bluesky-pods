#! /usr/bin/bash
set -e
set -o xtrace

# Set up local display and xhost access on Mac or Linux
# Check if the operating system is Mac or Linux
if [[ "$(uname)" == "Darwin" ]]; then
    # On a Mac, set LOCAL_DISPLAY_IP to the IP address
    LOCAL_DISPLAY_IP=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}')
elif [[ "$(uname)" == "Linux" ]]; then
    # On Linux, set LOCAL_DISPLAY_IP to an empty string
    LOCAL_DISPLAY_IP=""
fi
# Set LOCAL_DISPLAY
if [[ -n "$LOCAL_DISPLAY_IP" ]]; then
    LOCAL_DISPLAY="${LOCAL_DISPLAY_IP}:0"
else
    LOCAL_DISPLAY="$DISPLAY"
fi

# This was a useful reference for the $DISPLAY and xauth stuff.
# https://stackoverflow.com/a/48235281/1221924

if [ -z "SSH_CONNECTION" ]; then
	echo "SSH_CONNECTION is set"
	# Unlike the recommendation in the linked SO post,
	# we are not using docker and thus not using docker's special network.
	# Instead, we use the IP of the host.
	IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | head -n 1`
	DISPLAY=`echo $DISPLAY | sed "s/^[^:]*\(.*\)/${IP_ADDR}\1/"`
fi
if [[ "$(uname)" == "Darwin" ]]; then
    XAUTH=~/.Xauthority
else
    XAUTH=/tmp/.docker.xauth
fi
xauth nlist $LOCAL_DISPLAY | sed -e 's/^..../ffff/' | xauth -f $XAUTH nmerge -

# Get the IP adresses of all caproto IOC containers
containers=$(podman ps --filter name=caproto --format "{{.Names}}")
ca_containers=($containers)
EPICS_CA_ADDR_LIST=""

for container in "${ca_containers[@]}"; do
    container_ip=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container")
    echo "Adding $container_ip to EPICS_CA_ADDR_LIST"
    EPICS_CA_ADDR_LIST="$EPICS_CA_ADDR_LIST $container_ip"
done
EPICS_CA_ADDR_LIST=$(echo "$EPICS_CA_ADDR_LIST" | xargs)
EPICS_CA_ADDR_LIST="'$EPICS_CA_ADDR_LIST'"

# https://stackoverflow.com/questions/24112727/relative-paths-based-on-file-location-instead-of-current-working-directory
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

if [ -z "BLUESKY_PROFILE_DIR" ]; then
    echo "BLUESKY_PROFILE_DIR is set to $BLUESKY_PROFILE_DIR"
fi

if [ "$1" != "" ]; then
    imagename=$1
else
    imagename="bluesky"
fi

if [ "$2" != "" ]; then
    CMD=$2
else
    CMD="ipython3 --ipython-dir=/usr/local/share/ipython"
fi

#TODO (maffettone): fix EPICS_CA_ADDR_LIST
podman run --pod pod_acq-pod  \
       --net acq-pod_default \
       --network-alias sneaky \
       -ti  --rm \
       -v /tmp/.X11-unix/:/tmp/.X11-unix/ \
       -e DISPLAY=$LOCAL_DISPLAY \
       -v $XAUTH:/tmp/.docker.xauth \
       -e XAUTHORITY=/tmp/.docker.xauth \
       -v `pwd`:'/app' -w '/app' \
       -v ${BLUESKY_PROFILE_DIR:-$parent_path/../../bluesky_config/ipython/profile_default}:/usr/local/share/ipython/profile_default \
       -v $parent_path/../../bluesky_config/ipython/localdevs.py:/usr/local/share/ipython/localdevs.py \
       -v $parent_path/../../bluesky_config/databroker/mad.yml:/usr/local/share/intake/mad.yml \
       -v $parent_path/../../bluesky_config/databroker/mad-tiled.yml:/usr/etc/tiled/profiles/mad-tiled.yml \
       -v $parent_path/../../bluesky_config/happi:/usr/local/share/happi \
       -e XDG_RUNTIME_DIR=/tmp/runtime-$USER \
       -e EPICS_CA_ADDR_LIST="10.89.0.151 10.89.0.152 10.89.0.153 10.89.0.154 10.89.0.155 10.89.0.156 10.89.0.157" \
       -e EPICS_CA_AUTO_ADDR_LIST=no \
       -e PYTHONPATH=/usr/local/share/ipython\
       -e QSERVER_ZMQ_CONTROL_ADDRESS=tcp://queue_manager:60615\
       -e QSERVER_ZMQ_INFO_ADDRESS=tcp://queue_manager:60625\
       $imagename \
       $CMD \
