#! /usr/bin/bash
set -e
set -o xtrace

mkdir -p image_builders/pip_cache

container=$(buildah from bluesky-base)
# install some base python packages from pypi
buildah run $container -- dnf -y install  python3-pycurl
buildah run -v `pwd`/image_builders/pip_cache:/root/.cache/pip  $container -- pip3 install git+https://github.com/pcdshub/happi.git@master#egg=happi

# copy in source and install the current state of your checkout
targets=( ../event-model ../bluesky ../ophyd ../databroker ../bluesky-adaptive ../bluesky-queueserver ../suitcase-* ../bluesky-kafka)
for t in ${targets[@]}; do
    if test -f $t/setup.py; then
        t="$(basename -- $t)"
        # move the source into the container
        buildah copy $container ../$t /src/$t;
        # run the install
        buildah run -v `pwd`/image_builders/pip_cache:/root/.cache/pip  $container -- pip3 install /src/$t
        # nuke the source to save space?
        buildah run -v `pwd`/image_builders/pip_cache:/root/.cache/pip  $container -- rm -rf /src/$t
    fi
done

# install everything else ;)
buildah run -v `pwd`/image_builders/pip_cache:/root/.cache/pip  $container -- pip3 install nslsii

buildah run -v `pwd`/image_builders/pip_cache:/root/.cache/pip  $container -- pip3 uninstall --yes pyepics

buildah unmount $container
buildah commit $container bluesky-dev
