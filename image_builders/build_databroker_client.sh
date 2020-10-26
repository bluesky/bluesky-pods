
#! /usr/bin/bash
set -e
set -o xtrace

pushd ../databroker-client
npm install
npm run build
popd

container=$(buildah from nginx)
buildah copy $container ../databroker-client/build /var/www/html;
buildah unmount $container
buildah commit $container databroker-client
