
#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from condaforge/miniforge3)
# set up some config
buildah run $container -- apt update
buildah run $container -- apt-get --yes install mesa-utils patch
buildah run $container -- conda config --set always_yes yes --set changeps1 no --set quiet true
# pull the source from

buildah run $container -- conda create -n bluesky -c nsls2forge -c defaults --no-channel-priority --override-channels bluesky python=3.7 xpdan tomopy tqdm area-detector-handlers

buildah run -v `pwd`/image_builders/xpdan_patches:/patches $container -- bash -c "patch -d /opt/conda/envs/bluesky/lib/python3.7/site-packages/ -p1 < /patches/xpdan.patch"

buildah run -v `pwd`/image_builders/xpdan_patches:/patches $container -- bash -c "patch -d /opt/conda/envs/bluesky/lib/python3.7/site-packages/ -p1 < /patches/broker.patch"
buildah unmount $container
buildah commit $container xpdan
