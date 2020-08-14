#! /usr/bin/bash

set -o xtrace

podman pod stop acquisition
podman pod stop databroker

podman pod rm acquisition
podman pod rm databroker
