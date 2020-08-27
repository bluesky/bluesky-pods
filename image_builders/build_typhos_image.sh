#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from bluesky)
buildah run $container -- pip3 install typhos
buildah unmount $container
buildah commit $container typhos
