#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from bluesky-base)
buildah run $container -- pip3 install nslsii
buildah run $container -- pip3 install git+https://github.com/bluesky/bluesky-adaptive.git@main#egg=bluesky-adaptive
buildah run $container -- pip3 install git+https://github.com/bluesky/bluesky-queueserver.git@main#egg=bluesky-queueserver
buildah run $container -- pip3 install git+https://github.com/pcdshub/happi.git@master#egg=happi

buildah run $container -- pip3 uninstall --yes pyepics
buildah run $container -- mkdir /etc/bluesky
buildah copy $container image_builders/kafka.yml /etc/bluesky/kafka.yml
buildah unmount $container

buildah commit $container bluesky
