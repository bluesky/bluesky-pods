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

# Get the IP adresses of all caproto IOC containers; and list unique broadcast addresses. Should only be one.
# No assumption of ipcalc being available.
# Functions to convert an IP address to binary and back
ip_to_bin() {
    local ip="$1"
    IFS=. read -r a b c d <<< "$ip"
    printf "%08d%08d%08d%08d\n" "$(bc <<< "obase=2; $a")" "$(bc <<< "obase=2; $b")" "$(bc <<< "obase=2; $c")" "$(bc <<< "obase=2; $d")"
}
bin_to_ip() {
    local bin="$1"
    echo "$((2#${bin:0:8})).$((2#${bin:8:8})).$((2#${bin:16:8})).$((2#${bin:24:8}))"
}
containers=($(podman ps --filter name=caproto --format "{{.Names}}"))
EPICS_CA_ADDR_LIST=""
broadcasts=()
for container in "${containers[@]}"; do
    ip_address=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container")
    subnet_len=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPPrefixLen}}{{end}}' "$container")
    # Calculate the network mask in binary
    subnet_mask_bin=$(printf "%-32s" $(head -c $subnet_len < /dev/zero | tr '\0' '1'))
    subnet_mask_bin="${subnet_mask_bin// /0}"
    # Calculate the inverted subnet mask
    inv_subnet_mask_bin=$(echo "$subnet_mask_bin" | tr '01' '10')
    # Convert the IP address to binary
    ip_address_bin=$(ip_to_bin "$ip_address")
    # Calculate the network address (bitwise AND)
    network_address_bin=$(echo "$ip_address_bin" | awk -v mask="$subnet_mask_bin" '{for(i=1;i<=32;i++)printf "%d", substr($0,i,1) * substr(mask,i,1)}')
    # Calculate the broadcast address (bitwise OR with inverted subnet mask)
    broadcast_address_bin=$(echo "$network_address_bin" | awk -v inv_mask="$inv_subnet_mask_bin" '{for(i=1;i<=32;i++)printf "%d", substr($0,i,1) + substr(inv_mask,i,1)}')
    # Convert the broadcast address to a readable IP address
    broadcast_address=$(bin_to_ip "$broadcast_address_bin")
    broadcasts+=($broadcast_address)
done
uniques=($(for v in "${broadcasts[@]}"; do echo "$v";done| sort| uniq| xargs))
for addr in "${uniques[@]}"; do
    EPICS_CA_ADDR_LIST="$EPICS_CA_ADDR_LIST $addr"
done
EPICS_CA_ADDR_LIST="${EPICS_CA_ADDR_LIST:1}"
echo "EPICS_CA_ADDR_LIST=$EPICS_CA_ADDR_LIST"

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
       -e EPICS_CA_ADDR_LIST="${EPICS_CA_ADDR_LIST}" \
       -e EPICS_CA_AUTO_ADDR_LIST=no \
       -e PYTHONPATH=/usr/local/share/ipython\
       -e QSERVER_ZMQ_CONTROL_ADDRESS=tcp://queue_manager:60615\
       -e QSERVER_ZMQ_INFO_ADDRESS=tcp://queue_manager:60625\
       $imagename \
       $CMD \
