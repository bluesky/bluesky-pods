#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from bluesky)
buildah run $container -- python3 -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot"  # Build font cache.
buildah run $container -- pip3 install jupyterlab voila voila-material papermill ipympl databroker bluesky-live
buildah run $container -- pip3 install git+https://github.com/danielballan/papermillhub
buildah run $container -- jupyter serverextension enable voila --sys-prefix
buildah run $container -- jupyter serverextension enable papermillhub.nbext --sys-prefix
buildah run $container -- dnf install -y nodejs
buildah run $container -- jupyter labextension install @jupyter-widgets/jupyterlab-manager
buildah run $container -- jupyter labextension install jupyter-matplotlib
buildah run $container -- jupyter labextension install @jupyter-voila/jupyterlab-preview
buildah config --cmd "jupyter lab --no-browser --allow-root --NotebookApp.token='dev' --VoilaConfiguration.enable_nbextensions=True --VoilaConfiguration.template='material'" $container
buildah unmount $container
buildah commit $container jupyter
