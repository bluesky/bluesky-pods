
#! /usr/bin/bash
set -e
set -o xtrace

pushd ../bluesky-webclient
podman run --rm -v .:/src -w /src node:15.0.1-buster bash -c 'npm install && npm run build'
popd

container=$(buildah from docker.io/nginx)
buildah copy $container ../bluesky-webclient/build /var/www/html;
buildah unmount $container
buildah commit $container bluesky-webclient
