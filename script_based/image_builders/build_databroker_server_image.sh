#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from bluesky-base)
buildah run $container -- pip3 install git+https://github.com/bluesky/databroker-server.git@main#egg=databroker-server

buildah unmount $container
buildah commit $container databroker-server
