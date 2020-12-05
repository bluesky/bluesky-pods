#! /usr/bin/bash
set -e
set -o xtrace


podman run --pod acquisition \
       --rm -ti \
       -v ./bluesky_config/xpdacq/acq:/etc/acq \
       -v ./bluesky_config/databroker:/root/.local/share/intake \
       -v /mnt/store/data_cache/omnia:/data/omnia \
       -v /mnt/data/bnl/ae_exfil:/data/ae_exfil \
       xpdan \
       bash -c "/opt/conda/envs/bluesky/bin/analysis_server"
