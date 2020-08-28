#! /usr/bin/bash
set -e
set -o xtrace

container=$(buildah from bluesky-base)
buildah run $container -- dnf -y install python3-pycurl
# install some base python packages from pypi
buildah run $container -- pip3 install caproto[standard] jupyter httpie ipython fastapi uvicorn
buildah run $container -- pip3 install git+https://github.com/pcdshub/happi.git@master#egg=happi

# copy in source and install the current state of your checkout
targets=( ../event-model ../bluesky ../ophyd ../databroker ../bluesky-adaptive ../bluesky-queueserver ../suitcase-* )
for t in ${targets[@]}; do
    if test -f $t/setup.py; then
        t="$(basename -- $t)"
        # move the source into the container
        buildah copy $container ../$t /src/$t;
        # run the install
        buildah run $container -- pip3 install /src/$t
        # nuke the source to save space?
        buildah run $container -- rm -rf /src/$t
    fi
done

# install everything else ;)
buildah run $container -- pip3 install nslsii

buildah run $container -- pip3 uninstall --yes pyepics

buildah unmount $container
buildah commit $container bluesky-dev
