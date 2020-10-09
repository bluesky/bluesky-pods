
#! /usr/bin/bash
set -e
set -o xtrace

pushd ../bluesky-webclient
npm install
npm run build
popd

container=$(buildah from nginx)
buildah copy $container ../bluesky-webclient/build /var/www/html;
buildah unmount $container
buildah commit $container bluesky-webclient
