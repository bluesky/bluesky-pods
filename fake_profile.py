import logging
import uuid
import json
from functools import partial
from queue import Empty

import redis
import msgpack
import msgpack_numpy as mpn

from suitcase.mongo_normalized import Serializer
from bluesky import RunEngine
import bluesky.plans as bp


from bluesky.callbacks.best_effort import BestEffortCallback

from bluesky.callbacks.zmq import Publisher as zmqPublisher
from bluesky_kafka import Publisher as kafkaPublisher

from databroker._drivers.mongo_normalized import BlueskyMongoCatalog

from bluesky_adaptive.per_start import adaptive_plan

from ophyd.sim import *

RE = RunEngine()

mds = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
fs = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
serializer = Serializer(mds, fs)
catalog = BlueskyMongoCatalog(mds, fs)

zmq_publisher = zmqPublisher("127.0.0.1:4567")
kafka_publisher = kafkaPublisher(
    topic="all",
    bootstrap_servers="127.0.0.1:9092",
    key="kafka-unit-test-key",
    # work with a single broker
    producer_config={
        "acks": 1,
        "enable.idempotence": False,
        "request.timeout.ms": 5000,
    },
    serializer=partial(msgpack.dumps, default=mpn.encode),
)

bec = BestEffortCallback()

logger = logging.getLogger("databroker")
logger.setLevel("DEBUG")
handler = logging.StreamHandler()
handler.setLevel("DEBUG")
logger.addHandler(handler)

RE.subscribe(serializer)
RE.subscribe(zmq_publisher)
RE.subscribe(kafka_publisher)
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
