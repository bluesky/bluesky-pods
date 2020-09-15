#! /usr/bin/bash
set -e
set -o xtrace

bash start_acqusition_pod.sh
bash start_databroker_pod.sh
