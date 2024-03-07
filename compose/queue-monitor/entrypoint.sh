#!/bin/bash

echo "Starting queue-monitor GUI container..."
echo "Control address: $QSERVER_ZMQ_CONTROL_ADDRESS"
echo "Publish address: $QSERVER_ZMQ_INFO_ADDRESS"
echo "DISPLAY: $DISPLAY"
exec "$@"
