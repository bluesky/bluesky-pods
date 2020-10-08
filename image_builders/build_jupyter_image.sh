#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from bluesky)
buildah run $container -- pip3 install jupyterlab voila
buildah run $container -- jupyter serverextension enable voila --sys-prefix
buildah config --cmd "jupyter lab --no-browser --allow-root --NotebookApp.token=''" $container
buildah unmount $container
buildah commit $container jupyter
