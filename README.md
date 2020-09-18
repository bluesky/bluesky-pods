# Pods for bluesky(-adaptive)

This is a set of buildah and podman scripts that will stand up set of
pods that attempt to mimic the full beamline / remote compute model
(as we want to run at NSLS-II).

### Terms

- **image** : The binary blob that can be run as a container
- **container** : A running image.  You can have many containers
  running the same image simultaneously.  As part of starting the
  container you can pass in environmental variables and mount directories from
  the host into the container (read-only or read/write)
- **pod** : A collection of running containers that share a conceptual
  local network.  When the pod is created you can control which ports
  are visible to the host machine.  Internal to the pod ``localhost``
  can be used to access a container's peers and the IP address of the
  host to access exposed services from other pods.



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

## Configure for display over SSH

If the machine where you will be running podman is one you are connected to via
SSH, then you will need to configure the SSH daemon to accept connections routed
through podman---specifically, connections to its IP address rather than
`localhost`.

Add this line to `/etc/ssh/sshd_config`.

```
X11UseLocalhost no
```

If podman is running on the machine you are sitting in front of, or if you would like
to run in "headless" mode, no action is required.

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
pip install -r bluesky_config/scripts/requirements.txt
python bluesky_config/scripts/kafka_echo_consumer.py
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
http POST 0.0.0.0:60607/qs/create_environment
http POST 0.0.0.0:60607/qs/add_to_queue plan:='{"name":"count", "args":[["det1", "det2"]], "kwargs":{"num":10, "delay":1}}'
http POST 0.0.0.0:60607/qs/process_queue
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
