import json

import redis

from bluesky.callbacks.zmq import RemoteDispatcher
from bluesky_adaptive import recommendations
from bluesky_adaptive import per_start


d = RemoteDispatcher("127.0.0.1:5678", prefix=b"adaptive")


class RedisQueue:
    "fake just enough of the queue.Queue API on top of redis"

    def __init__(self, client):
        self.client = client

    def put(self, value):
        print(f"pushing {value}")
        self.client.lpush("adaptive", json.dumps(value))


rq = RedisQueue(redis.StrictRedis(host="localhost", port=6379, db=0))

adaptive_obj = recommendations.StepRecommender(1.5)
independent_keys = ["motor"]
dependent_keys = ["det"]
queue = rq
max_count = 15

rr, _ = per_start.recommender_factory(
    adaptive_obj, independent_keys, dependent_keys, max_count=max_count, queue=queue
)


d.subscribe(rr)
print("REMOTE IS READY TO START")
d.start()
