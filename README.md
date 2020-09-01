# Pods for bluesky(-adaptive)

This is a set of buildah and podman scripts that will stand up a pod that
can run a Bluesky session and an out-of-core adaptive plan

## Get podman

Podman and buildah are packaged on many Linux distributions. Refer to
[the official installation guide](https://podman.io/getting-started/installation)
for specific instructions. These instructions cover how to install `podman`.
Also install `buildah` in exactly the same fashion.

## Enable "rootless" usage

Unlike Docker, podman and buildah *can* be used without elevated privileges (i.e.
without `root` or a `docker` group). Podman only needs access to a range of uids
and gids to run processes in the container as a range of different "users".
Enable that like so:

```
sudo usermod --add-subuids 200000-201000 --add-subgids 200000-201000 $USER
podman system migrate
```

For additional details and troubleshooting, see
[the rootless tutorial](https://github.com/containers/podman/blob/master/docs/tutorials/rootless_tutorial.md).

## Build the containers

```sh
# this is fedora + some heavy weight Python
bash image_builders/build_bluesky_base_image.sh
# installs the rest of our stack on top of the base image
bash image_builders/build_bluesky_image.sh
# build an image with caproto installed
bash image_builders/build_caproto_image.sh
# build an image for the databroker server
bash image_builders/build_databroker_server_image.sh
# build an image with pydm / typhos installed
bash image_builders/build_typhos_image.sh
```

If you are feeling brave (and have the dependencies checked out as peers
of this directory) build a "snapshot" image via

```sh
bash image_builders/build_bluesky_snapshot.sh
```

## run the pod

```sh
# this sarts up caproto, mongo, zmqproxy, and redis
bash start_core_pod.sh
```

## .. manually

Run

```sh
bash launch_bluesky.sh
```

in a terminal or


```sh
bash launch_bluesky.sh bluesky-dev
```

to get the [what?]

## ...and watch from the outside

On your host machine run:

```bash
pip install -r bluesky_config/scripts/requirements.txt
python bluesky_config/scripts/kafka_echo_consumer.py
```

##  ...adaptively

Start the adaptive server:

```sh
bash start_adaptive_server.sh
```


Running in the shell should

```python
from ophyd.sim import *
RE(adaptive_plan([det], {motor: 0}, to_brains=to_brains, from_brains=from_brains))
```

should now take 17 runs stepping the motor by 1.5.  The data flow is

```
  | ---> kafka to the edge  --- /exposed ports on edge/ --> external consumers
  | ---> mongo
  | ---> live table
  |
  ^
  RE ---- kafka broker -----> adaptive_server
  ^                                  |
  | < -------- redis --------<-----< |

```

Maybe redis should be replaced by kafka?

The extra imports are because the motor and det that are set up by 00-base.py do not have
the keys that the adatptive code is expecting.


## ...queuely

and run

```python
RE(queue_server_plan())
```

On your host machine post to that end point (via
[httpie](https://httpie.org/) in this example):

```bash
http POST localhost:60607/qs/add_to_queue 'plan:={"plan":"scan", "args":[["pinhole"], "motor_ph", -10, 10, 25]}'
```

and watch the scans run!

The data flow is

```
  | ---> kafka to the edge ----------- /exposed ports on edge/ ---> external consumers
  | ---> mongo                                                                 |
  | ---> live table                                                            |
  ^                                                                            ↓
  RE < --- http --- queueserver < ---- / http from edge / <-------- http POST {json}


```
