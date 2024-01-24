
#! /usr/bin/bash
set -e
set -o xtrace

pushd ../databroker-client
podman run --rm -v .:/src -w /src node:15.0.1-buster bash -c 'npm install && npm run build'
popd

container=$(buildah from nginx)
buildah copy $container ../databroker-client/build /var/www/html;
buildah unmount $container
buildah commit $container databroker-client
