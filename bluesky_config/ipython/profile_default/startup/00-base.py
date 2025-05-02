import json
import logging
from functools import partial
from queue import Empty

import bluesky.plans as bp
import databroker
import happi
import happi.loader
import IPython
import matplotlib.pyplot as plt
import msgpack
import msgpack_numpy as mpn
import redis
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.callbacks.zmq import Publisher as zmqPublisher
from bluesky.plans import *
from bluesky_kafka import Publisher as kafkaPublisher
from bluesky_queueserver import is_re_worker_active

# from bluesky_adaptive.per_start import adaptive_plan # This is incompatible with the queue-server (default args)

ip = IPython.get_ipython()

hclient = happi.Client(path="/usr/local/share/happi/test_db.json")
db = databroker.catalog["MAD"]

RE = RunEngine()
bec = BestEffortCallback()

zmq_publisher = zmqPublisher("zmq-proxy:4567")
kafka_publisher = kafkaPublisher(
    topic="mad.bluesky.documents",
    bootstrap_servers="kafka:29092",
    key="kafka-unit-test-key",
    # work with a single broker
    producer_config={
        "acks": 1,
        "enable.idempotence": False,
        "request.timeout.ms": 5000,
    },
    serializer=partial(msgpack.dumps, default=mpn.encode),
)

logger = logging.getLogger("databroker")
logger.setLevel("DEBUG")
handler = logging.StreamHandler()
handler.setLevel("DEBUG")
logger.addHandler(handler)

RE.subscribe(zmq_publisher)
RE.subscribe(kafka_publisher)
RE.subscribe(bec)

to_recommender = kafkaPublisher(
    topic="adaptive",
    bootstrap_servers="kafka:9092",
    key="kafka-unit-test-key",
    # work with a single broker
    producer_config={
        "acks": 1,
        "enable.idempotence": False,
        "request.timeout.ms": 5000,
    },
    serializer=partial(msgpack.dumps, default=mpn.encode),
)


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
# you may have to run this twice to "prime the topics" the first time you run it
# RE(adaptive_plan([det], {motor: 0}, to_recommender=to_recommender, from_recommender=from_recommender))


devs = {v.name: v for v in [happi.loader.from_container(_) for _ in hclient.all_items]}

if ip is not None:
    ip.user_ns.update(devs)
elif is_re_worker_active():
    globals().update(devs)

# do from another
# http POST 0.0.0.0:8081/add_to_queue plan:='{"plan":"scan", "args":[["det"], "motor", -1, 1, 10]}'
# http POST 0.0.0.0:8081/add_to_queue plan:='{"plan":"count", "args":[["det"]]}'

plt.ion()
