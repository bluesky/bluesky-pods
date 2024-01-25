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

## Run the pod

```sh
cd compose/acq_pod
podman compose --in-pod true up
```

To get a bluesky terminal in this pod run

```sh
bash launch_bluesky.sh
```

There is a jupyterlab instance running in the pod available at
`http://localhost:11973/jlab`
