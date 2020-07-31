# Pods for bluesky(-adaptive)

This is a set of buildah and podman scripts that will stand up a pod that
can run a Bluesky session and an out-of-core adaptive plan

## Build the containers

```sh
# this is fedora + some heavy weight Python
bash uild_bluesky_base_image.sh
# installs the rest of our stack on top of the base image
bash build_bluesky_image.sh
# build an image with caproto installed
bash build_caproto_image.sh
```

## run the pod

```sh
# this sarts up caproto, mongo, zmqproxy, and redis
bash start_core_pod.sh
```

in one terminal

##  ...adaptively

```sh
bash start_adaptive_server.py
```

and in a second

```sh
bash launch_bluesky.sh
```


Running

```python
RE(adaptive_plan([det], {motor: 0}, to_brains=to_brains, from_brains=from_brains))
```

should now take 17 runs stepping the motor by 1.5.  The data flow is

```
  | ---> kafka to the edge
  | ---> mongo
  | ---> live table
  |
  RE ---- kafka broker -----> adaptive_server
  ^                                  |
  | < -------- redis --------<-----< |

```

Maybe redis should be replaced by kafka


## ...queuely

and in a second terminal

```sh
bash launch_bluesky.sh
```

and run

```python
RE(queue_sever_plan())
```

On your host machine run:

```bash
http POST localhost:60606/add_to_queue 'plan:={"plan":"scan", "args":[["pinhole"], "motor_ph", -10, 10, 25]}'
```

and watch the scans run!

## ...and watch from the outside

On your host machine run:

```bash
python kafka_echo_consumer.py
```
