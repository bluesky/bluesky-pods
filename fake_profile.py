import logging
import uuid
import json
from queue import Empty

import redis

from suitcase.mongo_normalized import Serializer
from bluesky import RunEngine
import bluesky.plans as bp


from bluesky.callbacks.zmq import Publisher
from bluesky.callbacks.best_effort import BestEffortCallback

from databroker._drivers.mongo_normalized import BlueskyMongoCatalog

from bluesky_adaptive.per_start import adaptive_plan

from ophyd.sim import *

RE = RunEngine()

mds = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
fs = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
serializer = Serializer(mds, fs)
catalog = BlueskyMongoCatalog(mds, fs)
p = Publisher("127.0.0.1:4567")
bec = BestEffortCallback()

logger = logging.getLogger("databroker")
logger.setLevel("DEBUG")
handler = logging.StreamHandler()
handler.setLevel("DEBUG")
logger.addHandler(handler)

RE.subscribe(serializer)
RE.subscribe(p)
RE.subscribe(bec)

to_brains = Publisher("127.0.0.1:4567", prefix=b"adaptive")


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


from_brains = RedisQueue(redis.StrictRedis(host="localhost", port=6379, db=0))

# RE(adaptive_plan([det], {motor: 0}, to_brains=to_brains, from_brains=from_brains))
