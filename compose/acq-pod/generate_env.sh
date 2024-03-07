#!/bin/bash
# Generate .env file for use with podman-compose
# Sets up local xauth rules for X11 forwarding

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
# If on a Mac, execute xhost + with LOCAL_DISPLAY_IP
if [[ "$(uname)" == "Darwin" ]]; then
    xhost +"$LOCAL_DISPLAY_IP"
fi

# This was a useful reference for the $DISPLAY and xauth stuff.
# https://stackoverflow.com/a/48235281/1221924
if [ -z "SSH_CONNECTION" ]; then
 	echo "SSH_CONNECTION is set"
 	# Unlike the recommendation in the linked SO post,
 	# we are not using docker and thus not using docker's special network.
 	# Instead, we use the IP of the host.
 	IP_ADDR=`ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | head -n 1`
 	LOCAL_DISPLAY=`echo $DISPLAY | sed "s/^[^:]*\(.*\)/${IP_ADDR}\1/"`
 fi
 if [[ "$(uname)" == "Darwin" ]]; then
     XAUTH=~/.Xauthority
 else
     XAUTH=/tmp/.docker.xauth
 fi
 xauth nlist $LOCAL_DISPLAY | sed -e 's/^..../ffff/' | xauth -f $XAUTH nmerge -

echo "LOCAL_DISPLAY_IP=$LOCAL_DISPLAY_IP" > .env
echo "LOCAL_DISPLAY=$LOCAL_DISPLAY" >> .env

