import msgpack
import msgpack_numpy as mpn
from functools import partial
from bluesky_kafka import RemoteDispatcher


kafka_dispatcher = RemoteDispatcher(
    topics=["adaptive"],
    bootstrap_servers="127.0.0.1:9092",
    group_id="kafka-unit-test-group-id",
    # "latest" should always work but
    # has been failing on Linux, passing on OSX
    consumer_config={"auto.offset.reset": "latest"},
    polling_duration=1.0,
    deserializer=partial(msgpack.loads, object_hook=mpn.decode),
)


def echo(name, doc):
    print(f"got a {name} document")


kafka_dispatcher.subscribe(echo)
kafka_dispatcher.start()
