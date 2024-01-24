# Script based pod management


## Build the images

```sh
# this is fedora + some heavy weight Python
bash image_builders/build_bluesky_base_image.sh
# installs the rest of our stack on top of the base image
bash image_builders/build_bluesky_image.sh
# build an image with caproto installed
bash image_builders/build_caproto_image.sh
# build an image for the databroker server
bash image_builders/build_databroker_server_image.sh
# build an image for the jupyter single-user server
bash image_builders/build_jupyter_image.sh
# build an image with pydm / typhos installed
bash image_builders/build_typhos_image.sh
```

If you are feeling brave (and have the dependencies checked out as peers
of this directory) build a "snapshot" image via

```sh
bash image_builders/build_bluesky_snapshot.sh
```


One way to manage container is a pod is to directly invoke
`podman` with the correct (and long) command line arguments either
directly in your shell or via shell scripts.

These scripts do not work out-of-the box any more due to errors in
paths (the bash scripts got pushed down a layer) and due to the
kafka config not being correct


## run the pod (script based)

```sh
# This starts:
#  Acquisition pod:
#     several caproto servers / synthetic IOCs
#     kafka (and published to edge)
#     zmq, mongo, redis (for internal use only)
#     queueserver
#     nginx (to proxy queueserver + static hosting)
#  Databroker pod:
#     kafka -> mongo client (looking at the Acqusition pod)
#     mongo (not exposed outside)
#     databroker server
#     nginx (to proxy services out)
# and mongo, kafka->mongo client, and the databroker server in the databroker pod
bash start_core_pods.sh
```

## Generate some example data quickly

```
podman run --rm --pod acquisition -v ./data_generation_scripts:/data_generation_scripts bluesky bash /data_generation_scripts/generate_example_data.sh
```

## Launch bsui (bluesky ipython terminal)

Run

```sh
bash launch_bluesky.sh
```

in a terminal or


```sh
bash launch_bluesky.sh bluesky-dev
```

to get the snapshot version.

or

```sh
bash launch_bluesky_headless.sh
```

for the version that does not require any graphics.

## ...and watch from the outside

On your host machine run:

```bash
pip install -r ../bluesky_config/scripts/requirements.txt
python ../bluesky_config/scripts/kafka_echo_consumer.py
```

##  Try an adaptive scan.

Start the adaptive server:

```sh
bash launchers/start_adaptive_server.sh
```


In the bsui terminal:

```python
from ophyd.sim import *
RE(adaptive_plan([det], {motor: 0}, to_recommender=to_recommender, from_recommender=from_recommender))
```

should now take 17 runs stepping the motor by 1.5.  The data flow is

```
  | ---> kafka to the edge  --- /exposed ports on edge/ --> external consumers
  | ---> live table
  |
  ^
  RE ---- kafka broker -----> adaptive_server
  ^            | ------> mongo       |
  | < -------- redis --------<-----< |

```

To view the results saved in mongo:

```python
db[-1]
```

Maybe redis should be replaced by kafka?

The extra imports are because the motor and det that are set up by 00-base.py do not have
the keys that the adatptive code is expecting.


## ...queuely

```bash
http POST 0.0.0.0:60610/qs/create_environment
http POST 0.0.0.0:60610/qs/add_to_queue plan:='{"name":"count", "args":[["det1", "det2"]], "kwargs":{"num":10, "delay":1}}'
http POST 0.0.0.0:60610/qs/process_queue
```

and watch the scans run!

See https://github.com/bluesky/bluesky-queueserver#features for more details of
how to run the queueserver

The data flow is

```
  | ---> kafka to the edge --------- /exposed ports on edge/ ---> external consumers
  |       | ---> internal mongo                                                |
  |                                                                            |
  | ---> live table                                                            |
  ^                                                                            ↓
  RE < --- http --- queueserver < --- / http from edge / <-------- http POST {json}


```
