import json
import logging
from functools import partial
from queue import Empty

import bluesky.plans as bp
import happi
import happi.loader
import IPython
import matplotlib.pyplot as plt
import redis
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.plans import *
from bluesky_queueserver import is_re_worker_active
from tiled.client import from_uri
from bluesky_tiled_plugins import TiledWriter, CatalogOfBlueskyRuns

# from bluesky_adaptive.per_start import adaptive_plan # This is incompatible with the queue-server (default args)

ip = IPython.get_ipython()

RE = RunEngine()

hclient = happi.Client(path="/usr/local/share/happi/test_db.json")

tiled_writing_client = c = from_uri("http://tiled:8000", api_key="secret")
tw = TiledWriter(tiled_writing_client)
RE.subscribe(tw)

c = CatalogOfBlueskyRuns(c.context, item=c.item, structure_clients=c.structure_clients)

bec = BestEffortCallback()


logger = logging.getLogger("databroker")
logger.setLevel("DEBUG")
handler = logging.StreamHandler()
handler.setLevel("DEBUG")
logger.addHandler(handler)

RE.subscribe(bec)

class RedisQueue:
    def __init__(self, client):
        self.client = client

    def put(self, value):
        self.client.lpush("adaptive", json.dumps(value))

    def get(self, timeout=0, block=True):
        if block:
            ret = self.client.blpop("adaptive", timeout=timeout)
            if ret is None:
                raise TimeoutError
            return json.loads(ret[1])
        else:
            ret = self.client.lpop("adaptive")
            if ret is not None:
                return json.loads(ret)
            else:
                raise Empty


from_recommender = RedisQueue(redis.StrictRedis(host="localhost", port=6379, db=0))

devs = {v.name: v for v in [happi.loader.from_container(_) for _ in hclient.all_items]}

if ip is not None:
    ip.user_ns.update(devs)
elif is_re_worker_active():
    globals().update(devs)

plt.ion()
