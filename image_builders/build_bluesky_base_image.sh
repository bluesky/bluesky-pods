#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from fedora)
buildah run $container -- dnf -y install python3 ipython3 python3-pip g++ gcc python3-PyQt5 python3-matplotlib python3-devel python3-netifaces python3-h5py python3-scipy python3-numcodecs python3-pandas libpng15 git python3-redis git python3-redis python3-scikit-image python3-zmq python3-pykafka python3-confluent-kafka python3-pymongo

buildah unmount $container
buildah commit $container bluesky-base
